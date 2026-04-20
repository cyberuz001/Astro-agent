"""
ASTRO V2.1 — Claude Code–style CLI UI
Powered by prompt_toolkit and rich.
"""
import asyncio
import os
import time
import threading
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.status import Status
from rich.theme import Theme
from rich.markdown import Markdown

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from astro_agent.agents.graph import astro_graph
from astro_agent.memory.chroma import memory_client
from astro_agent.memory.chats import (
    list_chats, load_chat, save_chat, delete_chat,
    new_chat_id, messages_to_dicts, dicts_to_messages,
)

# Set up custom Claude Code style theme
custom_theme = Theme({
    "astro": "bold #9ece6a",
    "user": "bold #7aa2f7",
    "system": "dim italic #565f89",
    "error": "bold #f7768e",
    "tool": "dim #e0af68",
    "menu": "#a9b1d6",
})
console = Console(theme=custom_theme)

prompt_style = Style.from_dict({
    # Prompt text
    'prompt': 'bold #7aa2f7',
    # Input area
    '': '#c0caf5',
})

SLASH_COMMANDS = {
    "/help": "Barcha buyruqlar",
    "/chats": "Saqlangan chatlar ro'yxati",
    "/new": "Yangi chat boshlash",
    "/open": "Chatni ochish (masalan: /open 1)",
    "/delete": "Chatni o'chirish (masalan: /delete 2)",
    "/clear": "Ekranni tozalash",
    "/deep on": "Chuqur fikrlash yoqish",
    "/deep off": "Chuqur fikrlash o'chirish",
    "/cloud": "Cloud modelga o'tish (OpenRouter)",
    "/local": "Lokal modelga o'tish (Ollama)",
    "/settings": "Sozlamalar",
}

class AstroApp:
    def __init__(self):
        completer = WordCompleter(list(SLASH_COMMANDS.keys()), ignore_case=True)
        self.session = PromptSession(style=prompt_style, completer=completer)
        self.chat_id = new_chat_id()
        self.chat_history = []
        self.chat_title = ""
        self.deep_thinking = False
        self.running = True

    def _monitor_voice_bridge(self):
        bridge = "/tmp/voice_bridge.txt"
        if not os.path.exists(bridge):
            try:
                open(bridge, "a").close()
                os.chmod(bridge, 0o666)
            except: pass
            
        with open(bridge, "r") as f:
            f.seek(0, os.SEEK_END)
            while self.running:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                
                with patch_stdout():
                    if "[User]" in line:
                        console.print(f"[user]📞 {line.replace('[User]', '').strip()}[/user]")
                    elif "[Agent]" in line:
                        console.print(f"[astro]🎤 {line.replace('[Agent]', '').strip()}[/astro]")
                    else:
                        console.print(f"[system]{line}[/system]")

    def run(self):
        # Start voice monitor thread
        threading.Thread(target=self._monitor_voice_bridge, daemon=True).start()

        # 1. Print Welcome Header
        console.print("\n[user]    ◆ Astro[/user] [dim]V2.1[/dim]")
        console.print("[dim]      Multi-Agent CLI Orchestrator[/dim]")
        console.print("[dim]      ~/.astro/chats[/dim]\n")
        console.print("[tool]  ✱[/tool] [dim]Type a message or use[/dim] [user]/help[/user] [dim]for commands[/dim]\n")

        # 2. Main Loop
        while True:
            try:
                with patch_stdout():
                    # Add newline before prompt for clean separation
                    user_input = self.session.prompt("❯ ").strip()
                    
                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if user_input == "/quit" or user_input == "/exit":
                        break
                    self._handle_command(user_input)
                    continue

                # Normal message
                self.chat_history.append(HumanMessage(content=user_input))
                if not self.chat_title:
                    self.chat_title = user_input[:50]

                self._execute_graph(user_input)

            except KeyboardInterrupt:
                # Ctrl+C clears prompt
                continue
            except EOFError:
                # Ctrl+D exits
                break
            except Exception as e:
                console.print(f"[error]Kutilmagan xatolik:[/] {e}")

    # ── Slash command router ──
    def _handle_command(self, raw: str):
        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            console.print("\n[menu][bold]━━ Command Palette ━━[/][/menu]")
            for c, d in SLASH_COMMANDS.items():
                console.print(f"  [user]{c:<20}[/] {d}")
            console.print()

        elif cmd == "/chats":
            chats = list_chats()
            if not chats:
                console.print("[system]Saqlangan chatlar topilmadi.[/system]")
                return
            console.print("\n[menu][bold]━━ Saqlangan Chatlar ━━[/][/menu]")
            for i, c in enumerate(chats, 1):
                ts = datetime.fromtimestamp(c["last_updated"]).strftime("%m/%d %H:%M")
                console.print(f"  [user]{i}.[/] {c['title'][:40]}  [dim]({c['message_count']} msg, {ts})[/]")
            console.print("[dim]/open <N> — ochish  ·  /delete <N> — o'chirish[/dim]\n")

        elif cmd == "/new":
            self._save_current_chat()
            self.chat_id = new_chat_id()
            self.chat_history = []
            self.chat_title = ""
            # os.system('clear')
            console.print("\n[system]Yangi chat boshlandi.[/system]\n")

        elif cmd == "/open":
            chats = list_chats()
            if not args or not args[0].isdigit():
                console.print("[error]Foydalanish: /open <raqam>[/error]")
                return
            idx = int(args[0]) - 1
            if idx < 0 or idx >= len(chats):
                console.print(f"[error]Chat #{args[0]} topilmadi.[/error]")
                return
            self._save_current_chat()
            c = load_chat(chats[idx]["id"])
            if not c:
                console.print("[error]Chat yuklashda xatolik.[/error]")
                return
            self.chat_id = c["id"]
            self.chat_title = c.get("title", "")
            self.chat_history = dicts_to_messages(c.get("messages", []))
            
            console.print(f"\n[system]Chat yuklandi: {self.chat_title}[/system]")
            # Print history
            for m in self.chat_history:
                if isinstance(m, HumanMessage):
                    console.print(f"\n[user]❯ You[/user]\n{m.content.strip()}")
                elif isinstance(m, AIMessage):
                    console.print(f"\n[astro]● Astro[/astro]")
                    console.print(Markdown(m.content.strip()))
            console.print()

        elif cmd == "/delete":
            chats = list_chats()
            if not args or not args[0].isdigit():
                console.print("[error]Foydalanish: /delete <raqam>[/error]")
                return
            idx = int(args[0]) - 1
            if idx < 0 or idx >= len(chats):
                console.print(f"[error]Chat #{args[0]} topilmadi.[/error]")
                return
            target = chats[idx]
            delete_chat(target["id"])
            console.print(f"[system]O'chirildi: {target['title'][:40]}[/system]")
            if target["id"] == self.chat_id:
                self.chat_id = new_chat_id()
                self.chat_history = []
                self.chat_title = ""

        elif cmd == "/clear":
            os.system('clear')

        elif cmd == "/deep":
            if args and args[0].lower() == "on":
                self.deep_thinking = True
                console.print("[system]Chuqur fikrlash [bold]yoqildi[/].[/system]")
            elif args and args[0].lower() == "off":
                self.deep_thinking = False
                console.print("[system]Chuqur fikrlash [bold]o'chirildi[/].[/system]")
            else:
                console.print("[system]Foydalanish: /deep on | /deep off[/system]")

        elif cmd == "/local":
            console.print("[system]Hozircha faqat lokal modellarga tayyorgarlik ko'rilmoqda...[/system]")
        elif cmd == "/cloud":
            console.print("[system]Cloud rejimida ishlanmoqda.[/system]")
        elif cmd == "/settings":
            console.print("[system]Sozlamalar paneli hali ishga tushirilmadi.[/system]")
        else:
            console.print(f"[error]Noma'lum buyruq: {cmd}  —  /help dan foydalaning[/error]")

    # ── LangGraph execution ──
    def _execute_graph(self, text: str):
        # We use a nice rich status spinner (dots natively match Claude's)
        out_content = ""
        tool_logs = []
        
        with Status("[astro]Astro[/astro]", spinner="point", spinner_style="bold #e0af68") as status:
            try:
                final_state = astro_graph.invoke({
                    "messages": self.chat_history,
                    "deep_think": self.deep_thinking,
                    "session_id": self.chat_id,
                })
                
                new_msgs = final_state["messages"][len(self.chat_history):]
                if new_msgs:
                    for m in new_msgs:
                        self.chat_history.append(m)
                        if isinstance(m, AIMessage):
                            if m.content:
                                out_content += m.content + "\n"
                            if hasattr(m, "tool_calls") and m.tool_calls:
                                for tc in m.tool_calls:
                                    tool_logs.append(f"{tc['name']}(...)")
                
                if out_content.strip():
                    try:
                        memory_client.memorize(self.chat_id, text, out_content.strip())
                    except:
                        pass
                self._save_current_chat()
            except Exception as e:
                console.print(f"[error]Astro Graph Error:[/] {e}")
                return

        # Print tools
        for tl in tool_logs:
            console.print(f"\n[tool]⚡ tool[/tool]\n{tl}")

        # Final AI output
        if out_content.strip():
            console.print("\n[astro]● Astro[/astro]")
            console.print(Markdown(out_content.strip()))
        console.print()  # Empty line separator

    def _save_current_chat(self):
        if not self.chat_history:
            return
        save_chat(self.chat_id, self.chat_title, dicts_to_messages([m.dict() for m in self.chat_history if hasattr(m, 'dict')]) if False else messages_to_dicts(self.chat_history), session_id=self.chat_id)
