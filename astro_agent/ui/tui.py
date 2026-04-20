"""
ASTRO V2.1 — Claude Code–style CLI UI
Powered by prompt_toolkit and rich.
"""
import os
import sys
import time
import threading
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
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

# ── Theme ──
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
    'prompt': 'bold #7aa2f7',
    '': '#c0caf5',
})

SLASH_COMMANDS = {
    "/help": "Barcha buyruqlar",
    "/chats": "Saqlangan chatlar ro'yxati",
    "/new": "Yangi chat boshlash",
    "/open": "Chatni ochish (/open 1)",
    "/delete": "Chatni o'chirish (/delete 2)",
    "/clear": "Ekranni tozalash",
    "/deep on": "Chuqur fikrlash yoqish",
    "/deep off": "Chuqur fikrlash o'chirish",
    "/madina": "Madina ovoziga o'tish (ayol)",
    "/sardor": "Sardor ovoziga o'tish (erkak)",
    "/cloud": "Cloud modelga o'tish",
    "/local": "Lokal modelga o'tish",
    "/settings": "Sozlamalar",
}


class SlashCompleter(Completer):
    """Only show completions when input starts with /"""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text), display_meta=desc)


class AstroApp:
    def __init__(self):
        self.session = PromptSession(style=prompt_style, completer=SlashCompleter())
        self.chat_id = new_chat_id()
        self.chat_history = []
        self.chat_title = ""
        self.deep_thinking = False
        self.running = True

    def _monitor_voice_bridge(self):
        from prompt_toolkit.application.current import get_app

        def safe_print(*args):
            app = get_app()
            if app and app.is_running:
                app.run_in_terminal(lambda: console.print(*args))
            else:
                console.print(*args)

        bridge = "/tmp/voice_bridge.txt"
        try:
            if not os.path.exists(bridge):
                open(bridge, "a").close()
                os.chmod(bridge, 0o666)
        except:
            pass
        try:
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
                    if "[User]" in line:
                        txt = line.replace('[User]', '').strip()
                        safe_print(f"[user]📞 {txt}[/user]")
                    elif "[Agent]" in line:
                        txt = line.replace('[Agent]', '').strip()
                        safe_print(f"[astro]🎤 {txt}[/astro]")
                    elif "Kiruvchi" in line or "Chiquvchi" in line:
                        safe_print("[system]━━ VoIP qo'ng'iroq boshlandi ━━[/system]")
                    elif "Yakunlandi" in line:
                        safe_print("[system]━━ Aloqa uzildi ━━[/system]")
                    else:
                        safe_print(f"[system]{line}[/system]")
        except:
            pass

    def run(self):
        threading.Thread(target=self._monitor_voice_bridge, daemon=True).start()

        console.print("\n[user]    ◆ Astro[/user] [dim]V2.1[/dim]")
        console.print("[dim]      Multi-Agent CLI Orchestrator[/dim]")
        console.print("[dim]      ~/.astro/chats[/dim]\n")
        console.print("[tool]  ✱[/tool] [dim]Type a message or use[/dim] [user]/help[/user] [dim]for commands[/dim]\n")

        while True:
            try:
                with patch_stdout():
                    user_input = self.session.prompt("❯ ").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if user_input in ("/quit", "/exit"):
                        break
                    self._handle_command(user_input)
                    continue

                self.chat_history.append(HumanMessage(content=user_input))
                if not self.chat_title:
                    self.chat_title = user_input[:50]

                self._execute_graph(user_input)

            except KeyboardInterrupt:
                # Ctrl+C exits the app
                console.print("\n[system]Sog' bo'ling![/system]")
                break
            except EOFError:
                break
            except Exception as e:
                console.print(f"[error]Kutilmagan xatolik:[/] {e}")

    # ── Slash commands ──
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
            console.print("[system]Lokal modellarga o'tilmoqda...[/system]")
        elif cmd == "/cloud":
            console.print("[system]Cloud rejimida ishlanmoqda.[/system]")
        elif cmd == "/settings":
            console.print("[system]Sozlamalar paneli hali ishga tushirilmadi.[/system]")
        elif cmd == "/madina":
            try:
                with open("/tmp/astro_voice.cfg", "w") as f:
                    f.write("uz-UZ-MadinaNeural")
                console.print("[astro]🎤 Ovoz: Madina (ayol) ga o'zgartirildi[/astro]")
            except:
                console.print("[error]Ovoz o'zgartirish xato[/error]")
        elif cmd == "/sardor":
            try:
                with open("/tmp/astro_voice.cfg", "w") as f:
                    f.write("uz-UZ-SardorNeural")
                console.print("[astro]🎤 Ovoz: Sardor (erkak) ga o'zgartirildi[/astro]")
            except:
                console.print("[error]Ovoz o'zgartirish xato[/error]")
        else:
            console.print(f"[error]Noma'lum buyruq: {cmd}  —  /help[/error]")

    # ── LangGraph execution ──
    def _execute_graph(self, text: str):
        tool_logs = []
        final_answer = ""

        with Status("[astro]Astro[/astro]", spinner="point", spinner_style="bold #e0af68"):
            try:
                final_state = astro_graph.invoke({
                    "messages": self.chat_history,
                    "deep_think": self.deep_thinking,
                    "session_id": self.chat_id,
                })

                new_msgs = final_state["messages"][len(self.chat_history):]
                for m in new_msgs:
                    self.chat_history.append(m)
                    if isinstance(m, AIMessage):
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                tool_logs.append(f"{tc['name']}(...)")

                # Only take the LAST AIMessage with content as the final answer
                for m in reversed(new_msgs):
                    if isinstance(m, AIMessage) and m.content:
                        final_answer = m.content.strip()
                        break

                if final_answer:
                    try:
                        memory_client.memorize(self.chat_id, text, final_answer)
                    except:
                        pass
                self._save_current_chat()
            except Exception as e:
                console.print(f"[error]Astro Graph Error:[/] {e}")
                return

        for tl in tool_logs:
            console.print(f"\n[tool]⚡ tool[/tool]\n{tl}")

        if final_answer:
            console.print("\n[astro]● Astro[/astro]")
            console.print(Markdown(final_answer))
        console.print()

    def _save_current_chat(self):
        if not self.chat_history:
            return
        save_chat(self.chat_id, self.chat_title, messages_to_dicts(self.chat_history), session_id=self.chat_id)
