#!/bin/bash
# ╔═══════════════════════════════════════════════╗
# ║  ASTRO Agent — Auto Installer                 ║
# ║  Autonomous AI Terminal & Voice Agent          ║
# ╚═══════════════════════════════════════════════╝

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "  ${CYAN}●${NC} $1"; }
ok()  { echo -e "  ${GREEN}✓${NC} $1"; }
err() { echo -e "  ${RED}✗${NC} $1"; }

echo ""
echo -e "  ${BOLD}${CYAN}◆ ASTRO Agent${NC} ${DIM}Installer${NC}"
echo -e "  ${DIM}Autonomous AI Terminal & Voice Agent${NC}"
echo ""

# ─── Check Python ──────────────────────────────────────────────────────────────
log "Python tekshirilmoqda..."
if ! command -v python3 &> /dev/null; then
    err "Python3 topilmadi! O'rnating: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
ok "Python3 topildi: $(python3 --version)"

# ─── Create Virtual Environment ───────────────────────────────────────────────
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$INSTALL_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    log "Virtual muhit yaratilmoqda..."
    python3 -m venv "$VENV_DIR"
    ok "Virtual muhit yaratildi"
else
    ok "Virtual muhit mavjud"
fi

# ─── Install Python Dependencies ──────────────────────────────────────────────
log "Python kutubxonalar o'rnatilmoqda..."
"$VENV_DIR/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
ok "Kutubxonalar o'rnatildi"

# ─── Install CLI ──────────────────────────────────────────────────────────────
log "ASTRO CLI o'rnatilmoqda..."
cat > /tmp/astro_launcher.sh << LAUNCHER
#!/bin/bash
exec "$VENV_DIR/bin/python3" "$INSTALL_DIR/astro.py" "\$@"
LAUNCHER
chmod +x /tmp/astro_launcher.sh
sudo cp /tmp/astro_launcher.sh /usr/local/bin/astro
rm /tmp/astro_launcher.sh
ok "CLI o'rnatildi: astro run"

# ─── API Key Setup ─────────────────────────────────────────────────────────────
echo ""
log "API kalitlarini sozlash"
mkdir -p "$HOME/.astro"

CONFIG_FILE="$HOME/.astro/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -n "  OpenRouter API kaliti (bo'sh qoldirish mumkin): "
    read -r OR_KEY
    echo -n "  OpenWeather API kaliti (bo'sh qoldirish mumkin): "
    read -r WEATHER_KEY

    cat > "$CONFIG_FILE" << CONFIGEOF
{
  "provider": "openrouter",
  "providers": {
    "openrouter": {
      "url": "https://openrouter.ai/api/v1/chat/completions",
      "key": "$OR_KEY",
      "model": "google/gemini-2.0-flash-lite-001"
    },
    "openai": {
      "url": "https://api.openai.com/v1/chat/completions",
      "key": "",
      "model": "gpt-4o-mini"
    },
    "local": {
      "url": "http://127.0.0.1:8080/v1/chat/completions",
      "key": "",
      "model": "gemma-4"
    }
  },
  "weather_api_key": "$WEATHER_KEY",
  "voice": "uz-UZ-MadinaNeural",
  "sudo_password": "password",
  "asterisk_call_target": "101"
}
CONFIGEOF
    ok "Konfiguratsiya saqlandi: $CONFIG_FILE"
else
    ok "Konfiguratsiya allaqachon mavjud"
fi

# ─── Asterisk PBX Setup ───────────────────────────────────────────────────────
echo ""
echo -n "  Asterisk PBX o'rnatilsinmi? (ha/yo'q) [yo'q]: "
read -r INSTALL_AST

if [[ "$INSTALL_AST" == "ha" ]]; then
    log "Asterisk o'rnatilmoqda..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq asterisk > /dev/null 2>&1
    ok "Asterisk o'rnatildi"

    # Extension range
    echo -n "  Raqamlar diapazoni (boshlanishi, masalan 100): "
    read -r EXT_START
    echo -n "  Raqamlar diapazoni (tugashi, masalan 110): "
    read -r EXT_END
    echo -n "  Standart parol (masalan: pass123): "
    read -r EXT_PASS

    EXT_START=${EXT_START:-100}
    EXT_END=${EXT_END:-110}
    EXT_PASS=${EXT_PASS:-pass123}

    log "pjsip.conf generatsiya qilinmoqda..."

    # Transport
    PJSIP_CONF="[transport-udp]\ntype=transport\nprotocol=udp\nbind=0.0.0.0:5060\n"

    # Extensions
    EXTENSIONS_CONF="[from-internal]\n"
    EXTENSIONS_CONF+="exten => 777,1,NoOp(Astro AGI)\n same => n,Ringing()\n same => n,Wait(3)\n same => n,Answer()\n same => n,AGI(antigravity.py)\n same => n,Hangup()\n\n"

    for ext in $(seq $EXT_START $EXT_END); do
        PJSIP_CONF+="\n[$ext]\ntype=endpoint\ncontext=from-internal\ndisallow=all\nallow=ulaw,alaw\nauth=$ext\naors=$ext\n"
        PJSIP_CONF+="\n[$ext]\ntype=auth\nauth_type=userpass\nusername=$ext\npassword=${EXT_PASS}\n"
        PJSIP_CONF+="\n[$ext]\ntype=aor\nmax_contacts=1\n"

        EXTENSIONS_CONF+="exten => $ext,1,Dial(PJSIP/$ext,30,tTrR)\n same => n,Hangup()\n\n"
    done

    # Wildcard patterns
    EXTENSIONS_CONF+="exten => _1XX,1,Dial(PJSIP/\${EXTEN},30,tTrR)\n same => n,Hangup()\n"
    EXTENSIONS_CONF+="exten => _1XXX,1,Dial(PJSIP/\${EXTEN},30,tTrR)\n same => n,Hangup()\n"

    echo -e "$PJSIP_CONF" | sudo tee /etc/asterisk/pjsip.conf > /dev/null
    echo -e "$EXTENSIONS_CONF" | sudo tee /etc/asterisk/extensions.conf > /dev/null

    ok "pjsip.conf yaratildi ($EXT_START-$EXT_END raqamlar, parol: $EXT_PASS)"
    ok "extensions.conf yaratildi (777=AGI, ichki qo'ng'iroqlar)"

    # Install AGI
    log "AGI voice engine o'rnatilmoqda..."
    sudo cp "$INSTALL_DIR/agi/antigravity.py" /usr/share/asterisk/agi-bin/antigravity.py
    sudo chmod +x /usr/share/asterisk/agi-bin/antigravity.py
    ok "AGI o'rnatildi"

    # Install edge-tts for asterisk user
    log "edge-tts o'rnatilmoqda..."
    "$VENV_DIR/bin/pip" install -q edge-tts
    ok "edge-tts o'rnatildi"

    # Download Vosk model
    if [ ! -d "/usr/share/asterisk/vosk-model" ]; then
        log "Vosk STT modeli yuklanmoqda (bu biroz vaqt olishi mumkin)..."
        cd /tmp
        wget -q https://alphacephei.com/vosk/models/vosk-model-small-uz-0.22.zip -O vosk-uz.zip 2>/dev/null || true
        if [ -f vosk-uz.zip ]; then
            unzip -qo vosk-uz.zip
            sudo mv vosk-model-small-uz-0.22 /usr/share/asterisk/vosk-model
            rm vosk-uz.zip
            ok "Vosk modeli o'rnatildi"
        else
            err "Vosk modelini yuklab bo'lmadi (keyinroq qo'lda o'rnating)"
        fi
    else
        ok "Vosk modeli allaqachon mavjud"
    fi

    # Restart Asterisk
    sudo systemctl restart asterisk 2>/dev/null || sudo asterisk -rx "core restart now" 2>/dev/null || true
    ok "Asterisk qayta ishga tushirildi"
fi

# ─── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}${BOLD}✓ O'rnatish yakunlandi!${NC}"
echo ""
echo -e "  ${DIM}Ishga tushirish:${NC}  ${BOLD}astro run${NC}"
echo -e "  ${DIM}API sozlash:${NC}     ${BOLD}astro run${NC} → ${CYAN}/api set openrouter <key>${NC}"
echo -e "  ${DIM}Yordam:${NC}          ${BOLD}astro run${NC} → ${CYAN}/help${NC}"
echo ""
