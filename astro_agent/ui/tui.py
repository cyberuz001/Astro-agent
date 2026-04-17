"""
ASTRO V2.1 — Claude Code–style Terminal UI
Modeled after Claude Code's actual terminal interface.
"""
import asyncio
import uuid
import time
import os
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Static, Input, Label
from textual.reactive import reactive
from textual.binding import Binding
from textual import work, on
from textual.worker import get_current_worker
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from astro_agent.agents.graph import astro_graph
from astro_agent.memory.chroma import memory_client
from astro_agent.memory.chats import (
    list_chats, load_chat, save_chat, delete_chat,
    new_chat_id, messages_to_dicts, dicts_to_messages,
)

# ── All slash commands for autocomplete ────────────────────────────────────────
SLASH_COMMANDS = [
    ("/help",       "Barcha buyruqlar ro'yxatini ko'rsatish"),
    ("/chats",      "Saqlangan chatlar ro'yxatini ko'rish"),
    ("/new",        "Yangi chat boshlash"),
    ("/open",       "Saqlangan chatni ochish (masalan: /open 1)"),
    ("/delete",     "Chatni o'chirish (masalan: /delete 2)"),
    ("/clear",      "Ekranni tozalash"),
    ("/deep on",    "Chuqur fikrlash rejimini yoqish"),
    ("/deep off",   "Chuqur fikrlash rejimini o'chirish"),
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Claude Code–style CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CSS = """
Screen {
    background: #1a1b26;
    color: #a9b1d6;
}

/* ── Welcome banner at top ── */
#welcome-banner {
    height: auto;
    padding: 1 2;
    background: #1a1b26;
    color: #a9b1d6;
}

/* ── Chat scroll area ── */
#chat-scroll {
    height: 1fr;
    padding: 0 2;
    background: #1a1b26;
    scrollbar-size: 1 1;
    scrollbar-color: #414868;
    scrollbar-color-hover: #565f89;
    scrollbar-color-active: #7aa2f7;
}

/* ── Separator line above input ── */
#separator {
    height: 1;
    background: #1a1b26;
    color: #414868;
    padding: 0 2;
}

/* ── Slash command suggestions panel ── */
#suggestions {
    height: auto;
    max-height: 12;
    padding: 0 2;
    background: #24283b;
    display: none;
}

.suggestion-item {
    height: 1;
    padding: 0 1;
    color: #a9b1d6;
}

.suggestion-cmd {
    color: #7aa2f7;
    width: 24;
}

.suggestion-desc {
    color: #565f89;
}

/* ── Input bar ── */
#input-bar {
    height: 3;
    padding: 0 2;
    background: #1a1b26;
}

#prompt-label {
    width: 4;
    color: #7aa2f7;
    padding: 1 0 0 0;
    text-style: bold;
}

#user-input {
    background: transparent;
    border: none;
    color: #c0caf5;
    width: 1fr;
    padding: 0 0;
}

#user-input:focus {
    border: none;
}

/* ── Status line ── */
#status-line {
    height: 1;
    background: #16161e;
    color: #565f89;
    padding: 0 2;
    dock: bottom;
}

/* ── Message styles ── */
.msg-user {
    margin: 1 0 0 0;
    padding: 0 0;
    color: #c0caf5;
}

.msg-ai {
    margin: 0 0 1 0;
    padding: 0 0;
    color: #a9b1d6;
}

.msg-system {
    margin: 1 0;
    padding: 0 0;
    color: #565f89;
    text-style: italic;
}

.msg-error {
    margin: 1 0;
    padding: 0 0;
    color: #f7768e;
}

.msg-tool {
    margin: 0 0;
    padding: 0 2;
    color: #e0af68;
    text-style: dim;
}

.msg-menu {
    margin: 1 0;
    padding: 1 2;
    color: #a9b1d6;
    background: #24283b;
}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AstroApp
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AstroApp(App):
    CSS = CSS
    TITLE = "Astro"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Exit"),
        Binding("ctrl+n", "new_chat", "New Chat"),
    ]

    deep_thinking = reactive(False)

    def compose(self) -> ComposeResult:
        # Welcome banner (like Claude Code header)
        yield Static(id="welcome-banner")
        # Chat scroll
        yield VerticalScroll(id="chat-scroll")
        # Separator
        yield Static("─" * 120, id="separator")
        # Slash command suggestions (hidden by default)
        yield Static(id="suggestions")
        # Input bar
        with Horizontal(id="input-bar"):
            yield Label("❯ ", id="prompt-label")
            yield Input(placeholder="", id="user-input")
        # Status line at bottom
        yield Static(id="status-line")

    def on_mount(self) -> None:
        self.query_one("#user-input", Input).focus()
        self.chat_id = new_chat_id()
        self.chat_history = []
        self.chat_title = ""
        self._render_welcome()
        self._update_status("READY")
        # PBX voice monitor
        self.start_voice_monitor()

    def _render_welcome(self):
        banner = self.query_one("#welcome-banner", Static)
        banner.update(
            "[bold #7aa2f7]    ◆ Astro[/bold #7aa2f7] [dim]V2.1[/dim]\n"
            "[dim]      Multi-Agent TUI Orchestrator[/dim]\n"
            "[dim]      ~/.astro/chats[/dim]\n\n"
            "[#e0af68]  ✱[/] [dim]Type a message or use[/] [bold #7aa2f7]/help[/] [dim]for commands[/]\n"
        )

    def _update_status(self, state: str):
        bar = self.query_one("#status-line", Static)
        dt = datetime.now().strftime("%H:%M")
        deep = "on" if self.deep_thinking else "off"
        chat_label = self.chat_title[:28] if self.chat_title else "new chat"
        bar.update(f" {state} · {chat_label} · deep:{deep} · {dt}")

    # ── Message rendering ──────────────────────────────────────────────────
    def _post(self, role: str, content: str):
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        cls_map = {
            "user": "msg-user", "ai": "msg-ai",
            "system": "msg-system", "error": "msg-error",
            "tool": "msg-tool", "menu": "msg-menu",
        }
        cls = cls_map.get(role, "msg-system")
        prefix_map = {
            "user":   "[bold #7aa2f7]❯[/] [bold #c0caf5]You[/]",
            "ai":     "[bold #9ece6a]◆[/] [bold #9ece6a]Astro[/]",
            "system": "[dim #565f89]⚙[/] [dim]system[/dim]",
            "error":  "[bold #f7768e]✖[/] [bold #f7768e]error[/]",
            "tool":   "[dim #e0af68]⚡ tool[/]",
            "menu":   "",
        }
        prefix = prefix_map.get(role, "")
        if prefix:
            text = f"{prefix}\n{content}"
        else:
            text = content
        scroll.mount(Static(text, classes=cls))
        scroll.scroll_end(animate=False)

    def _save_current_chat(self):
        if not self.chat_history:
            return
        if not self.chat_title:
            for m in self.chat_history:
                if isinstance(m, HumanMessage):
                    self.chat_title = m.content[:50]
                    break
            if not self.chat_title:
                self.chat_title = "Untitled"
        save_chat(self.chat_id, self.chat_title,
                  messages_to_dicts(self.chat_history), session_id=self.chat_id)

    def _clear_display(self):
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        for w in list(scroll.children):
            w.remove()

    # ── Actions ────────────────────────────────────────────────────────────
    def action_new_chat(self):
        self._do_new_chat()

    def _do_new_chat(self):
        self._save_current_chat()
        self.chat_id = new_chat_id()
        self.chat_history = []
        self.chat_title = ""
        self._clear_display()
        self._post("system", "Yangi chat boshlandi.")
        self._update_status("READY")

    # ── Voice monitor ──────────────────────────────────────────────────────
    @work(thread=True)
    def start_voice_monitor(self):
        worker = get_current_worker()
        bridge = Path("/tmp/voice_bridge.txt")
        if not bridge.exists():
            bridge.touch()
        try:
            os.chmod(str(bridge), 0o666)
        except Exception:
            pass
        with open(bridge, "r") as f:
            f.seek(0, 2)
            while not worker.is_cancelled:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                if "[User]" in line:
                    self.call_from_thread(self._post, "user", f"📞 {line.replace('[User]','').strip()}")
                elif "[Agent]" in line:
                    self.call_from_thread(self._post, "ai", f"🎤 {line.replace('[Agent]','').strip()}")
                elif "Kiruvchi" in line or "Chiquvchi" in line:
                    self.call_from_thread(self._post, "system", "VoIP qo'ng'iroq boshlandi")
                elif "Yakunlandi" in line:
                    self.call_from_thread(self._post, "system", "Aloqa uzildi")

    # ── Slash command suggestions (Claude Code style) ──────────────────────
    @on(Input.Changed, "#user-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        val = event.value.strip()
        suggestions_widget = self.query_one("#suggestions", Static)
        if val.startswith("/") and not " " in val:
            # Filter matching commands
            matches = [
                (cmd, desc) for cmd, desc in SLASH_COMMANDS
                if cmd.startswith(val)
            ]
            if matches:
                lines = []
                for cmd, desc in matches:
                    lines.append(f"  [#7aa2f7]{cmd:<24}[/] [dim]{desc}[/]")
                suggestions_widget.update("\n".join(lines))
                suggestions_widget.styles.display = "block"
            else:
                suggestions_widget.styles.display = "none"
        else:
            suggestions_widget.styles.display = "none"

    # ── Slash command router ───────────────────────────────────────────────
    def _handle_command(self, raw: str) -> bool:
        parts = raw.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            lines = ["[bold]━━ Command Palette ━━[/]\n"]
            for c, d in SLASH_COMMANDS:
                lines.append(f"  [#7aa2f7]{c:<20}[/] {d}")
            self._post("menu", "\n".join(lines))
            return True

        elif cmd == "/chats":
            chats = list_chats()
            if not chats:
                self._post("system", "Saqlangan chatlar topilmadi.")
                return True
            lines = ["[bold]━━ Saqlangan Chatlar ━━[/]\n"]
            for i, c in enumerate(chats, 1):
                ts = datetime.fromtimestamp(c["last_updated"]).strftime("%m/%d %H:%M")
                lines.append(
                    f"  [#7aa2f7]{i}.[/] {c['title'][:40]}"
                    f"  [dim]({c['message_count']} msg, {ts})[/]"
                )
            lines.append("\n[dim]/open <N> — ochish  ·  /delete <N> — o'chirish[/]")
            self._post("menu", "\n".join(lines))
            return True

        elif cmd == "/new":
            self._do_new_chat()
            return True

        elif cmd == "/open":
            return self._cmd_open(args)

        elif cmd == "/delete":
            return self._cmd_delete(args)

        elif cmd == "/clear":
            self._clear_display()
            self.chat_history = []
            self.chat_title = ""
            self.chat_id = new_chat_id()
            self._post("system", "Tozalandi.")
            self._update_status("READY")
            return True

        elif cmd == "/deep":
            if args and args[0].lower() == "on":
                self.deep_thinking = True
                self._post("system", "Chuqur fikrlash [bold]yoqildi[/].")
            elif args and args[0].lower() == "off":
                self.deep_thinking = False
                self._post("system", "Chuqur fikrlash [bold]o'chirildi[/].")
            else:
                self._post("system", "Foydalanish: /deep on | /deep off")
            self._update_status("READY")
            return True

        elif cmd.startswith("/"):
            self._post("error", f"Noma'lum buyruq: {cmd}  —  /help")
            return True

        return False

    def _cmd_open(self, args) -> bool:
        chats = list_chats()
        if not args or not args[0].isdigit():
            self._post("error", "Foydalanish: /open <raqam>")
            return True
        idx = int(args[0]) - 1
        if idx < 0 or idx >= len(chats):
            self._post("error", f"Chat #{args[0]} topilmadi. /chats ni ko'ring.")
            return True
        self._save_current_chat()
        c = load_chat(chats[idx]["id"])
        if not c:
            self._post("error", "Chat yuklash xatolik.")
            return True
        self._clear_display()
        self.chat_id = c["id"]
        self.chat_title = c.get("title", "")
        self.chat_history = dicts_to_messages(c.get("messages", []))
        for m in self.chat_history:
            if isinstance(m, HumanMessage):
                self._post("user", m.content)
            elif isinstance(m, AIMessage):
                self._post("ai", m.content)
        self._post("system", f"Chat yuklandi: {self.chat_title}")
        self._update_status("READY")
        return True

    def _cmd_delete(self, args) -> bool:
        chats = list_chats()
        if not args or not args[0].isdigit():
            self._post("error", "Foydalanish: /delete <raqam>")
            return True
        idx = int(args[0]) - 1
        if idx < 0 or idx >= len(chats):
            self._post("error", f"Chat #{args[0]} topilmadi.")
            return True
        target = chats[idx]
        delete_chat(target["id"])
        self._post("system", f"O'chirildi: {target['title'][:40]}")
        if target["id"] == self.chat_id:
            self._do_new_chat()
        return True

    # ── Input submitted ────────────────────────────────────────────────────
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value
        event.input.value = ""
        # Hide suggestions
        self.query_one("#suggestions", Static).styles.display = "none"

        if not raw.strip():
            return

        if raw.strip().startswith("/"):
            self._handle_command(raw.strip())
            return

        # Regular message
        self._post("user", raw)
        self.chat_history.append(HumanMessage(content=raw))
        if not self.chat_title:
            self.chat_title = raw[:50]
        self._update_status("THINKING")
        self.execute_graph(raw)

    # ── LangGraph worker ──────────────────────────────────────────────────
    @work(thread=True)
    def execute_graph(self, text: str):
        try:
            final_state = astro_graph.invoke({
                "messages": self.chat_history,
                "deep_think": self.deep_thinking,
                "session_id": self.chat_id,
            })
            new_msgs = final_state["messages"][len(self.chat_history):]
            out_content = ""
            if new_msgs:
                for m in new_msgs:
                    self.chat_history.append(m)
                    if isinstance(m, AIMessage):
                        if m.content:
                            out_content += m.content + "\n"
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                self.call_from_thread(
                                    self._post, "tool",
                                    f"{tc['name']}({str(tc['args'])[:80]})"
                                )
                if out_content.strip():
                    self.call_from_thread(self._post, "ai", out_content.strip())
                    try:
                        memory_client.memorize(self.chat_id, text, out_content.strip())
                    except Exception:
                        pass
            self.call_from_thread(self._save_current_chat)
        except Exception as e:
            self.call_from_thread(self._post, "error", f"LangGraph: {e}")
        self.call_from_thread(self._update_status, "READY")
