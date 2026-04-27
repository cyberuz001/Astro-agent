#!/bin/bash

# Animator/Spinner funksiyasi
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while kill -0 $pid 2>/dev/null; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

echo -e "\e[1;36m==================================================\e[0m"
echo -e "\e[1;36m         ASTRO V2.0 O'RNATISH YORDAMCHISI         \e[0m"
echo -e "\e[1;36m==================================================\e[0m"
echo ""

# Sudo ruxsatini oldindan so'rab olish va saqlab qolish
echo -e "\e[1;33mO'rnatish jarayoni administrator (root) ruxsatlarini talab qiladi.\e[0m"
sudo -v
# Sudo ruxsatini fonda yangilab turuvchi tsikl
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# Asterisk o'rnatish haqida so'rash
echo -e "\e[1;33mAsterisk VoIP tizimi o'rnatilsinmi? Ushbu tizim orqali Astro qo'ng'iroqlarni amalga oshira oladi.\e[0m"
read -p "(y/n): " install_asterisk

declare -a ext_numbers

if [[ "$install_asterisk" == "y" || "$install_asterisk" == "Y" ]]; then
    read -p "Nechta raqam qo'shmoqchisiz? (masalan, 3): " num_exts
    if [[ "$num_exts" =~ ^[0-9]+$ ]] && [ "$num_exts" -gt 0 ]; then
        for (( i=1; i<=$num_exts; i++ ))
        do
            read -p "$i-chi raqamni kiriting (masalan, 10$i): " ext_num
            ext_numbers+=("$ext_num")
        done
        echo -e "\e[1;32mRaqamlar qabul qilindi.\e[0m"
    else
        echo -e "\e[1;31mNoto'g'ri son kiritildi. Asterisk raqamlarsiz o'rnatiladi.\e[0m"
    fi
fi

echo ""
echo -e "\e[1;34m[1/4] Tizim paketlarini yangilash va tayyorlash...\e[0m"
(
    sudo apt-get update -y
    sudo apt-get install -y python3-venv python3-pip
) > /dev/null 2>&1 &
spinner $!
echo -e "\e[1;32m✅ Tizim tayyor.\e[0m"

if [[ "$install_asterisk" == "y" || "$install_asterisk" == "Y" ]]; then
    echo -e "\e[1;34m[2/4] Asterisk o'rnatilmoqda va sozlanmoqda (bu biroz vaqt olishi mumkin)...\e[0m"
    (
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y asterisk

        # Konfiguratsiya
        if [ ${#ext_numbers[@]} -gt 0 ]; then
            PJSIP_CONF="/etc/asterisk/pjsip.conf"
            EXT_CONF="/etc/asterisk/extensions.conf"

            # Backup
            if [ ! -f "${PJSIP_CONF}.bak" ] && [ -f "$PJSIP_CONF" ]; then
                sudo cp "$PJSIP_CONF" "${PJSIP_CONF}.bak"
            fi
            if [ ! -f "${EXT_CONF}.bak" ] && [ -f "$EXT_CONF" ]; then
                sudo cp "$EXT_CONF" "${EXT_CONF}.bak"
            fi

            # Transport UDP
            if ! sudo grep -q "\[transport-udp\]" $PJSIP_CONF 2>/dev/null; then
                echo -e "\n[transport-udp]\ntype=transport\nprotocol=udp\nbind=0.0.0.0" | sudo tee -a $PJSIP_CONF > /dev/null
            fi

            for ext in "${ext_numbers[@]}"; do
                sudo bash -c "cat >> $PJSIP_CONF <<EOF

[$ext]
type=endpoint
context=from-internal
disallow=all
allow=ulaw
auth=auth$ext
aors=$ext

[auth$ext]
type=auth
auth_type=userpass
password=pass$ext
username=$ext

[$ext]
type=aor
max_contacts=1
EOF"

                # Extensions.conf ga sodda dialplan qo'shish
                if ! sudo grep -q "\[from-internal\]" $EXT_CONF 2>/dev/null; then
                    echo -e "\n[from-internal]" | sudo tee -a $EXT_CONF > /dev/null
                fi
                sudo bash -c "echo 'exten => $ext,1,Dial(PJSIP/$ext,20)' >> $EXT_CONF"
                sudo bash -c "echo 'exten => $ext,2,Hangup()' >> $EXT_CONF"
            done

            sudo systemctl restart asterisk || true
        fi
    ) > /dev/null 2>&1 &
    spinner $!
    echo -e "\e[1;32m✅ Asterisk o'rnatildi va sozlandi.\e[0m"
else
    echo -e "\e[1;34m[2/4] Asterisk o'tkazib yuborildi.\e[0m"
fi

echo -e "\e[1;34m[3/4] Python virtual muhiti (venv) yaratilmoqda...\e[0m"
(
    python3 -m venv venv
) > /dev/null 2>&1 &
spinner $!
echo -e "\e[1;32m✅ Virtual muhit yaratildi.\e[0m"

echo -e "\e[1;34m[4/4] Kerakli kutubxonalar (pip packages) o'rnatilmoqda...\e[0m"
(
    source venv/bin/activate
    pip install --upgrade pip
    pip install textual langgraph langchain-community langchain-openai chromadb sentence-transformers duckduckgo-search cryptography requests
) > /dev/null 2>&1 &
spinner $!
echo -e "\e[1;32m✅ Kutubxonalar o'rnatildi.\e[0m"

echo -e "\e[1;34mSo'nggi sozlamalar yakunlanmoqda...\e[0m"
chmod +x astro.py
sudo cp astro.py /usr/local/bin/astro

echo -e "\e[1;36m==================================================\e[0m"
echo -e "\e[1;32m✅ Barcha jarayonlar muvaffaqiyatli yakunlandi!\e[0m"
echo -e "\e[1;32m   'astro run' buyrug'ini tering.\e[0m"
echo -e "\e[1;36m==================================================\e[0m"
