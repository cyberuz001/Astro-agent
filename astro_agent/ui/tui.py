import asyncio
import uuid
import time
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll, Vertical
from textual.widgets import Header, Footer, Static, Input, Switch, Label
from textual.reactive import reactive
from textual.binding import Binding
from textual import work
from textual.worker import get_current_worker
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from astro_agent.agents.graph import astro_graph
from astro_agent.memory.chroma import memory_client

# ─── Claude Code–style dark TUI CSS ───────────────────────────────────────────
CSS = """
Screen {
    background: #0d1117;
    color: #e6edf3;
}

#sidebar {
    width: 32;
    dock: right;
    background: #161b22;
    padding: 1 2;
    border-left: vkey #30363d;
}

#chat-container {
    padding: 1 3;
    height: 1fr;
    background: transparent;
}

#input-container {
    height: 3;
    dock: bottom;
    padding: 0 1;
    border-top: solid #30363d;
    background: #161b22;
}

Input {
    background: transparent;
    border: none;
    padding: 0 1;
    color: #58a6ff;
}
Input:focus { border: none; }

/* ── Semantic message bubbles ── */
.user-msg {
    margin: 1 0 1 10;
    padding: 1 2;
    color: #8b949e;
    text-align: right;
    border-right: thick #6e7681;
}

.astro-msg {
    margin: 1 10 1 0;
    padding: 1 2;
    color: #c9d1d9;
    background: #1c2128;
    border-left: thick #58a6ff;
}

.system-msg {
    margin: 1 5;
    padding: 0 2;
    color: #ab7df8;
    text-align: left;
    text-style: italic;
    border-left: thick #ab7df8;
}

.error-msg {
    margin: 1 5;
    padding: 1 2;
    color: #f85149;
    background: #3e1b1e;
    border-left: thick #f85149;
}

/* ── Status Orb ── */
#status-orb {
    content-align: center middle;
    width: 100%;
    height: 3;
    color: #238636;
    border: solid #238636;
    margin-top: 1;
}

.thinking {
    color: #d29922;
    border: solid #d29922;
}

/* ── Matrix background layer ── */
#matrix-bg {
    width: 100%;
    height: 100%;
    color: #238636;
    opacity: 0.12;
    layer: background;
}

.box { padding: 0 1; }
"""

# ─── Header widget ─────────────────────────────────────────────────────────────
class CyberHeader(Static):
    def render(self) -> str:
        return "[bold #58a6ff]◆ ASTRO V2.1[/bold #58a6ff] | [dim]Multi-Agent TUI Orchestrator[/dim] | [italic]Type /help[/italic]"

# ─── Animated Matrix Rain ──────────────────────────────────────────────────────
class MatrixRain(Static):
    def on_mount(self):
        self._rain = [
            "  010101110001   1 0 11  01  0 011  01 1010  1  0  ",
            "    1101   10101  0   10 101 0   0 11 1   10  1 0  ",
            "  11 1 01 0   11   01  0 10  0 1000  01 01  11  0  ",
            "   01 1 10 110  1 00  1 1 00  0 0  10 11 0  01  1  "
        ]
        self._step = 0
        self.update("\n".join(self._rain))
        self.set_interval(0.8, self.tick)

    def tick(self):
        self._step += 1
        n = len(self._rain)
        shifted = self._rain[self._step % n:] + self._rain[:self._step % n]
        self.update("\n".join(shifted))

# ─── Chat history scroll pane ──────────────────────────────────────────────────
class MessageLog(VerticalScroll):
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AstroApp  –  the main application
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AstroApp(App):
    CSS = CSS
    BINDINGS = [Binding("ctrl+c", "quit", "Exit", show=True)]

    deep_thinking_enabled = reactive(False)

    # ── Layout ─────────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield MatrixRain(id="matrix-bg")
        yield Header(show_clock=True)
        yield CyberHeader(classes="box")

        with Container():
            with Horizontal():
                with Vertical(id="chat-container"):
                    yield MessageLog(id="chat-history")

                with Vertical(id="sidebar"):
                    yield Label("[bold]⚙️ Settings Palette[/bold]\n")
                    yield Label("Deep Reflection:")
                    yield Switch(value=False, id="deep-think-toggle")
                    yield Label("\nMulti-Agent Sync:")
                    yield Switch(value=True, id="multi-agent-toggle", disabled=True)
                    yield Label("\n[bold]System Status:[/bold]")
                    yield Static("● READY", id="status-orb")

        with Horizontal(id="input-container"):
            yield Label("astro ❯ ", id="prompt-icon")
            yield Input(placeholder="Type commands or /help...", id="user-input")
        yield Footer()

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def on_mount(self) -> None:
        self.query_one("#user-input").focus()
        self.session_id = str(uuid.uuid4())[:8]
        self.chat_history = []

        welcome_msg = (
            "Dizayn yangilandi. Command-line orchestrator aktiv.\n"
            "Mavjud buyruqlar uchun [bold #58a6ff]/help[/] deb yozing."
        )
        self.add_message("System", welcome_msg)

        # Start PBX voice monitor daemon (thread worker)
        self.start_voice_monitor()

    # ── Voice Bridge daemon ────────────────────────────────────────────────
    @work(thread=True)
    def start_voice_monitor(self):
        """Monitor /tmp/voice_bridge.txt for PBX events."""
        worker = get_current_worker()
        bridge = Path("/tmp/voice_bridge.txt")
        if not bridge.exists():
            bridge.touch()
        try:
            os.chmod(str(bridge), 0o666)
        except Exception:
            pass

        with open(bridge, "r") as f:
            f.seek(0, 2)  # seek to end
            while not worker.is_cancelled:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                # Parse voice events
                if "[User]" in line:
                    self.call_from_thread(self.add_message, "User", f"📞 User aytdi: {line.replace('[User]', '').strip()}")
                elif "[Agent]" in line:
                    self.call_from_thread(self.add_message, "Astro", f"🎤 AI javob berdi: {line.replace('[Agent]', '').strip()}")
                elif "Kiruvchi" in line or "Chiquvchi" in line:
                    self.call_from_thread(self.add_message, "System", "[yellow]VoIP Qo'ng'iroq jarayoni boshlandi.[/yellow]")
                elif "Yakunlandi" in line:
                    self.call_from_thread(self.add_message, "System", "[red]Aloqa uzildi.[/red]")

    # ── Orb state ──────────────────────────────────────────────────────────
    def set_thinking(self, state: bool):
        orb = self.query_one("#status-orb")
        if state:
            orb.update("● EXECUTION")
            orb.add_class("thinking")
        else:
            orb.update("● READY")
            orb.remove_class("thinking")

    # ── Toggle handler ─────────────────────────────────────────────────────
    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "deep-think-toggle":
            self.deep_thinking_enabled = event.value
            self.add_message("System", f"Astro Agent Reflection rejimiga o'tdi: {event.value}")

    # ── Message renderer ───────────────────────────────────────────────────
    def add_message(self, role: str, content: str):
        log = self.query_one("#chat-history", MessageLog)
        if role == "User":
            cls = "user-msg"
            title = "[dim]👤 User[/dim]"
        elif role == "System":
            cls = "system-msg"
            title = "[bold #ab7df8]⚡ Tizim xabari[/bold #ab7df8]"
        elif role == "Error":
            cls = "error-msg"
            title = "[bold #f85149]✖ Xatolik[/bold #f85149]"
        else:
            cls = "astro-msg"
            title = "[bold #58a6ff]🤖 Astro Engine[/bold #58a6ff]"

        log.mount(Static(f"{title}\n{content}", classes=cls))
        log.scroll_end(animate=False)

    # ── Command palette ────────────────────────────────────────────────────
    def handle_slash_command(self, cmd: str) -> bool:
        c = cmd.lower().strip()
        if c == "/clear":
            log = self.query_one("#chat-history", MessageLog)
            for widget in list(log.children):
                widget.remove()
            self.chat_history = []
            self.add_message("System", "Chat tarixi va kontekst tozalandi.")
            return True
        elif c == "/help":
            help_txt = (
                "[bold]Command Palette (Astro Orchestrator)[/bold]\n"
                "• [yellow]/help[/]   - Mavjud buyruqlarni ko'rsatish\n"
                "• [yellow]/clear[/]  - Chat va kontekstni tozalash\n"
                "• [yellow]/deep on[/] - Chuqur fikrlash (Reflection) yoqish\n"
                "• [yellow]/deep off[/]- Chuqur fikrlashni o'chirish\n"
                "\nBarcha qolgan matnlar avtomatik AI agentga jo'natiladi."
            )
            self.add_message("System", help_txt)
            return True
        elif c == "/deep on":
            self.query_one("#deep-think-toggle").value = True
            return True
        elif c == "/deep off":
            self.query_one("#deep-think-toggle").value = False
            return True
        elif c.startswith("/"):
            self.add_message("Error", f"Noma'lum buyruq: {c}. /help orqali ro'yxatni ko'ring.")
            return True
        return False

    # ── Input handler ──────────────────────────────────────────────────────
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        u_in = event.value
        event.input.value = ""
        if not u_in.strip():
            return

        # Slash commands are handled on main thread (UI-only)
        if u_in.startswith("/"):
            self.handle_slash_command(u_in)
            return

        self.add_message("User", u_in)
        self.chat_history.append(HumanMessage(content=u_in))

        self.set_thinking(True)
        # ⬇ THIS is the critical fix — just call the @work-decorated method
        self.execute_graph(u_in)

    # ── LangGraph worker (runs in BACKGROUND THREAD) ──────────────────────
    @work(thread=True)
    def execute_graph(self, text: str):
        """Invoke LangGraph orchestrator in a background thread."""
        try:
            final_state = astro_graph.invoke({
                "messages": self.chat_history,
                "deep_think": self.deep_thinking_enabled,
                "session_id": self.session_id
            })

            new_msgs = final_state["messages"][len(self.chat_history):]
            if new_msgs:
                out_content = ""
                for m in new_msgs:
                    self.chat_history.append(m)
                    if isinstance(m, AIMessage):
                        if m.content:
                            out_content += m.content + "\n"
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                self.call_from_thread(
                                    self.add_message,
                                    "System",
                                    f"⚡ Executing: {tc['name']} {str(tc['args'])[:100]}"
                                )

                if out_content.strip():
                    self.call_from_thread(self.add_message, "Astro", out_content.strip())
                    try:
                        memory_client.memorize(self.session_id, text, out_content.strip())
                    except Exception:
                        pass
        except Exception as e:
            self.call_from_thread(self.add_message, "Error", f"LangGraph Orchestrator Failure: {e}")
        self.call_from_thread(self.set_thinking, False)
