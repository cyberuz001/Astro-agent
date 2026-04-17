# ◆ ASTRO Agent

**Autonomous AI Terminal & Voice Agent for Asterisk PBX**

ASTRO is an open-source AI agent that combines a powerful terminal interface with Asterisk PBX voice capabilities. It can manage your server, make phone calls, check weather, and much more — all through natural Uzbek language interaction.

## Features

- 🤖 **AI-Powered Terminal** — Claude Code-style CLI with tool execution
- 📞 **Voice Calls** — Make and receive AI-powered phone calls via Asterisk PBX
- 🌤️ **Weather & Time** — Get real-time weather and time for any city worldwide
- 🔧 **Server Admin** — Manage Asterisk, SIP extensions, passwords, and configs
- 🔑 **Multi-Provider** — OpenRouter, OpenAI, Local LLM support
- 🇺🇿 **Uzbek Language** — Native Uzbek TTS (Madina/Sardor voices) and STT

## Quick Start

```bash
git clone https://github.com/cyberuz/astro-agent.git
cd astro-agent
chmod +x install.sh
./install.sh
astro run
```

## Commands

| Command | Description |
|---------|-------------|
| `/api` | Show API providers and keys |
| `/api set openrouter <key>` | Set OpenRouter API key |
| `/api set openai <key>` | Set OpenAI API key |
| `/api set weather <key>` | Set OpenWeather API key |
| `/api use <provider>` | Switch active provider |
| `/api model <name>` | Change model |
| `/voice madina` | Switch to Madina voice |
| `/voice sardor` | Switch to Sardor voice |
| `/clear` | Clear conversation history |
| `/exit` | Exit |

## Project Structure

```
astro-agent/
├── astro.py              # Main CLI application
├── agi/
│   └── antigravity.py    # Asterisk AGI voice engine
├── install.sh            # Auto-installer with Asterisk wizard
├── requirements.txt      # Python dependencies
└── README.md
```

## Configuration

Config is stored at `~/.astro/config.json`:

```json
{
  "provider": "openrouter",
  "providers": {
    "openrouter": { "url": "...", "key": "your-key", "model": "..." },
    "openai": { "url": "...", "key": "", "model": "gpt-4o-mini" },
    "local": { "url": "http://127.0.0.1:8080/...", "key": "", "model": "gemma-4" }
  },
  "weather_api_key": "your-openweather-key",
  "voice": "uz-UZ-MadinaNeural"
}
```

## Asterisk Setup

The installer can automatically:
1. Install Asterisk PBX
2. Generate `pjsip.conf` with your extension range
3. Generate `extensions.conf` with internal routing + AGI
4. Download Vosk Uzbek STT model
5. Install edge-tts for TTS

## Requirements

- Python 3.10+
- Linux (Ubuntu/Debian recommended)
- Asterisk PBX (optional, for voice features)

## License

MIT License
