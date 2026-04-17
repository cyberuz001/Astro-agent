import asyncio
import uuid
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll, Vertical
from textual.widgets import Header, Footer, Static, Input, Switch, Label
from textual.reactive import reactive
from textual.binding import Binding
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Load specific modules
from astro_agent.agents.graph import astro_graph
from astro_agent.memory.chroma import memory_client

CSS = """
Screen { background: #0d1117; color: #c9d1d9; }
#sidebar { width: 30; dock: right; background: #161b22; padding: 1; border-left: vkey #30363d; }
#chat-container { padding: 1 2; height: 1fr; background: transparent; }
#input-container { height: 4; dock: bottom; padding: 0 1; border-top: solid #30363d; background: #161b22; }
Input { background: transparent; border: none; padding: 0 1; color: #58a6ff; }
Input:focus { border: none; }
.user-msg { margin: 1 0; padding: 0 1; color: #8b949e; text-align: right; }
.astro-msg { margin: 1 0; padding: 0 1; color: #c9d1d9; background: #21262d; border-left: thick #58a6ff; }
#status-orb { content-align: center middle; width: 3; height: 1; color: #238636; }
.thinking { animation: pulse 1.5s linear infinite; color: #d29922; }
@keyframes pulse { 0% { opacity: 1.0; } 50% { opacity: 0.3; } 100% { opacity: 1.0; } }
#matrix-bg { width: 100%; height: 100%; color: #00ff00; opacity: 0.1; layer: background; }
.box { padding: 0; margin: 0; content-align: left middle; }
"""

class CyberHeader(Static):
    def render(self) -> str:
        return "[bold #58a6ff]◆ ASTRO V2.0[/bold #58a6ff] | [dim]Autonomous Cybernetic Engine[/dim]"

class MatrixRain(Static):
    def on_mount(self):
        self._rain = [
            "101011001010  01   11",
            "  0101011101  10  1  ",
            "1 0  0100 11  01 001 ",
            "001 1  00 000 10  01 ",
            " 10101 00  10 1  0 0 "
        ]
        self._step = 0
        self.update("\\n".join(self._rain))
        self.set_interval(0.3, self.tick)

    def tick(self):
        self._step += 1
        shifted = self._rain[self._step % len(self._rain):] + self._rain[:self._step % len(self._rain)]
        self.update("\\n".join(shifted))

class MessageLog(VerticalScroll):
    id = "chat-history"

class AstroApp(App):
    CSS = CSS
    BINDINGS = [Binding("ctrl+c", "quit", "Chiqish", show=True)]
    
    is_thinking = reactive(False)
    deep_thinking_enabled = reactive(False)
    
    def compose(self) -> ComposeResult:
        yield MatrixRain(id="matrix-bg")
        yield Header(show_clock=True)
        yield CyberHeader(classes="box")
        with Container():
            with Horizontal():
                with Vertical(id="chat-container"):
                    yield MessageLog()
                with Vertical(id="sidebar"):
                    yield Label("[bold]⚙️ Sozlamalar[/bold]\\n")
                    yield Label("Chuqur Fikrlash:")
                    yield Switch(value=False, id="deep-think-toggle")
                    yield Label("\\nHolat:")
                    yield Static("● Kutish", id="status-orb")
                    
        with Horizontal(id="input-container"):
            yield Label("astro ❯ ", id="prompt-icon")
            yield Input(placeholder="Terminal yoki Tizim buyruqlarini yozing...", id="user-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#user-input").focus()
        self.session_id = str(uuid.uuid4())[:8]
        self.chat_history = []
        self.add_message("Tizim", "ASTRO V2.0 tizimga to'liq ulandi. Serveringiz sizning ixtiyoringizda. Men har qanday amalni administrator huquqida (sudo) bajara olaman.")
        
        # Start PBX Voice Monitoring in background
        self.run_worker(self.voice_monitor_task(), thread=True)

    def voice_monitor_task(self):
        import time, os
        from pathlib import Path
        bridge = Path("/tmp/voice_bridge.txt")
        if not bridge.exists(): bridge.touch()
        try: os.chmod(str(bridge), 0o666)
        except: pass
        
        with open(bridge, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line: continue
                if "[User]" in line:
                    self.call_from_thread(self.add_message, "Siz", f"📞 {line.replace('[User]', '').strip()}")
                elif "[Agent]" in line:
                    self.call_from_thread(self.add_message, "Astro", f"🎤 {line.replace('[Agent]', '').strip()}")
                elif "Kiruvchi" in line or "Chiquvchi" in line:
                    self.call_from_thread(self.add_message, "Astro", f"[yellow]VoIP Qo'ng'iroq faollashdi.[/yellow]")
                elif "Yakunlandi" in line:
                    self.call_from_thread(self.add_message, "Tizim", f"[red]Aloqa yakunlandi.[/red]")

    def add_message(self, role: str, content: str):
        log = self.query_one(MessageLog)
        cls = "user-msg" if role == "Siz" else "astro-msg"
        name = "[dim]👤 Siz[/dim]" if role == "Siz" else "[bold #58a6ff]🤖 Astro[/bold #58a6ff]"
        
        msg_widget = Static(f"{name}\\n{content}", classes=cls)
        log.mount(msg_widget)
        log.scroll_end(animate=False)

    def set_thinking(self, state: bool):
        self.is_thinking = state
        orb = self.query_one("#status-orb")
        if state:
            orb.update("● O'ylanmoqda")
            orb.add_class("thinking")
        else:
            orb.update("● Ochiq")
            orb.remove_class("thinking")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "deep-think-toggle":
            self.deep_thinking_enabled = event.value

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        u_in = event.value
        event.input.value = ""
        if not u_in.strip(): return
        
        self.add_message("Siz", u_in)
        self.chat_history.append(HumanMessage(content=u_in))
        
        self.set_thinking(True)
        self.run_worker(self.execute_graph(u_in), thread=True)

    def execute_graph(self, text: str):
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
                            out_content += m.content + "\\n"
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                self.call_from_thread(self.add_message, "Astro", f"⚡ {tc['name']} {tc['args']}")
                    
                if out_content.strip():
                    self.call_from_thread(self.add_message, "Astro", out_content.strip())
                    # Persist final interaction securely
                    try:
                        memory_client.memorize(self.session_id, text, out_content.strip())
                    except: pass
        except Exception as e:
            self.call_from_thread(self.add_message, "Tizim", f"[red]API Xatosi (Graph LLM): {e}[/red]")
        self.call_from_thread(self.set_thinking, False)
