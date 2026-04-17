#!/usr/bin/env python3
"""
ASTRO Agent V2.0 — Textual TUI & LangGraph Hub Entrypoint
https://github.com/cyberuz/astro-agent
"""

import sys
import os
sys.path.insert(0, "/home/user/astro-agent")

try:
    from astro_agent.core.config import ensure_sudo
except ModuleNotFoundError:
    print("Xato: astro_agent modul papkasi topilmadi. O'rnatishni tekshiring.")
    sys.exit(1)

def main():
    # 1. Ask securely for sudo if not cached
    ensure_sudo()
    
    # 2. Launch Textual Dashboard natively
    from astro_agent.ui.tui import AstroApp
    app = AstroApp()
    app.run()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        main()
    else:
        print("\033[36m◆ ASTRO V2.0 (LangGraph + Textual Core)\033[0m")
        print("Barcha komponentlar modul yordamida tashkil qilindi.")
        print("Ishga tushirish uchun yozing: astro run")
