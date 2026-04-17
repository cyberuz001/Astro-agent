#!/usr/bin/env python3
"""
ASTRO Agent V2.0 — Textual TUI & LangGraph Hub
https://github.com/cyberuz/astro-agent
"""
import sys, os, time, json, asyncio, subprocess, threading, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Annotated, Sequence, TypedDict, Literal, Optional
import requests

# ─── Config ────────────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".astro"
CONFIG_FILE = CONFIG_DIR / "config.json"
VOICE_FILE  = Path("/tmp/astro_voice.cfg")
BRIDGE_FILE = Path("/tmp/voice_bridge.txt")
CONTEXT_FILE = Path("/tmp/agi_outbound_context.txt")
RESULT_FILE  = Path("/tmp/agi_mission_result.txt")

DEFAULT_CONFIG = {
    "provider": "openrouter",
    "providers": {
        "openrouter": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": "",
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
    "weather_api_key": "",
    "voice": "uz-UZ-MadinaNeural",
    "sudo_password": "password",
    "asterisk_call_target": "101"
}

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            # Merge with defaults
            for k, v in DEFAULT_CONFIG.items():
                if k not in saved:
                    saved[k] = v
            return saved
        except: pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()



# ─── Dependencies ──────────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, VerticalScroll, Vertical
    from textual.widgets import Header, Footer, Static, Input, Switch, Label, Markdown, RichLog
    from textual.reactive import reactive
    from textual.binding import Binding
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
    from langgraph.graph import StateGraph, END, START
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
except ImportError:
    print("❌ Kerakli kutubxonalar topilmadi. O'rnating: pip install textual langgraph langchain-openai langchain-community chromadb sentence-transformers duckduckgo-search requests pydantic")
    sys.exit(1)

# ─── MEMORY (ChromaDB) ───────────────────────────────────────────────────


# Create default storage path for Chroma DB
MEMORY_DIR = Path.home() / ".astro" / "memory"

    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    
        def __init__(self):
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(MEMORY_DIR))
            # Use a lightweight multilingual sentence transformer for fast CPU execution
            self.collection = self.client.get_or_create_collection(
                name="astro_conversations",
                metadata={"hnsw:space": "cosine"}
            )
            # Embedding model loader lazily
            self.model = None

        def _get_model(self):
            if self.model is None:
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            return self.model

        def memorize(self, session_id: str, human_text: str, ai_text: str):
            """Saves a conversation turn into ChromaDB"""
            doc = f"User: {human_text}\nAstro: {ai_text}"
            embedding = self._get_model().encode([doc]).tolist()
            doc_id = f"{session_id}_{len(self.collection.get()['ids'])}"
            
            self.collection.add(
                ids=[doc_id],
                embeddings=embedding,
                documents=[doc],
                metadatas=[{"session": session_id}]
            )

        def recall(self, query: str, k=3) -> str:
            """Retrieves top-K similar past conversations"""
            if self.collection.count() == 0:
                return ""
                
            query_emb = self._get_model().encode([query]).tolist()
            results = self.collection.query(
                query_embeddings=query_emb,
                n_results=min(k, self.collection.count())
            )
            
            if not results['documents'][0]:
                return ""
            
            context = "O'tmishdagi suhbatlardan xotira parchalar:\n"
            for doc in results['documents'][0]:
                context += f"---\n{doc}\n"
            return context

    memory_client = LongTermMemory()

        def memorize(self, *args, **kwargs): pass
        def recall(self, *args, **kwargs): return ""
    memory_client = DummyMemory()

MEMORY_DIR = Path.home() / ".astro" / "memory"
class LongTermMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(MEMORY_DIR))
        self.collection = self.client.get_or_create_collection(
            name="astro_conversations",
            metadata={"hnsw:space": "cosine"}
        )
        self.model = None

    def _get_model(self):
        if self.model is None:
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return self.model

    def memorize(self, session_id: str, human_text: str, ai_text: str):
        doc = f"User: {human_text}\nAstro: {ai_text}"
        embedding = self._get_model().encode([doc]).tolist()
        doc_id = f"{session_id}_{len(self.collection.get()['ids'])}"
        self.collection.add(
            ids=[doc_id],
            embeddings=embedding,
            documents=[doc],
            metadatas=[{"session": session_id}]
        )

    def recall(self, query: str, k=3) -> str:
        if self.collection.count() == 0:
            return ""
        query_emb = self._get_model().encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_emb,
            n_results=min(k, self.collection.count())
        )
        if not results['documents'] or not results['documents'][0]:
            return ""
        context = "O'tmishdagi suhbatlardan xotira parchalar:\n"
        for doc in results['documents'][0]:
            context += f"---\n{doc}\n"
        return context

try: memory_client = LongTermMemory()
except: 
    class DummyMemory:
        def memorize(self, *args, **kwargs): pass
        def recall(self, *args, **kwargs): return ""
    memory_client = DummyMemory()

# ─── Tools ─────────────────────────────────────────────────────────────────────
def sudo_cmd(cmd):
    pwd = config.get("sudo_password", "password")
    if "sudo " in cmd and "-S" not in cmd:
        cmd = cmd.replace("sudo ", f"echo '{pwd}' | sudo -S ")
    return cmd

def run_cmd(command):
    try:
        command = command.strip()
        if command.startswith("asterisk "):
            command = "sudo " + command
        command = sudo_cmd(command)
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()[:4000] or "(buyruq bajarildi, natija bo'sh)"
    except Exception as e:
        return f"Xato: {e}"

def get_weather_and_time(location, iana_timezone="Asia/Tashkent"):
    time_str = ""
    try:
        if "time_now_offset" not in locals():
            tz_req = requests.get(f"https://time.now/developer/api/timezone/{iana_timezone}", timeout=5).json()
            if "datetime" in tz_req:
                dt_iso = tz_req["datetime"]
                # Manual parsing: 2026-04-17T16:13:00.123456+05:00
                date_part, time_part = dt_iso.split("T")
                time_part = time_part[:5] # "16:13"
                y, m, d = date_part.split("-")
                months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
                time_str = f"{y}-yil {int(d)}-{months[int(m)-1]}, soat {time_part}"
    except:
        time_str = "Vaqtni aniqlab bo'lmadi."

    try:
        api_key = config.get("weather_api_key", "") if "config" in globals() else WEATHER_API_KEY
        if api_key:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric&lang=uz"
            data = requests.get(url, timeout=8).json()
            if data.get("cod") == 200:
                temp = data["main"]["temp"]
                desc = data["weather"][0]["description"]
                weather_str = f"Ob-havo: harorat {temp}°C, {desc}."
                return f"{location}: {time_str}. {weather_str}"
            else:
                return f"{location}: {time_str}. Ob-havo aniqlanmadi."
        return f"{location}: {time_str}."
    except Exception as e:
        return f"Xato: {e}"

def make_voice_call(message, mission_goal=None):
    try:
        if RESULT_FILE.exists(): RESULT_FILE.unlink()
        
        Path("/tmp/agi_outbound_msg.txt").write_text(message)
        os.chmod("/tmp/agi_outbound_msg.txt", 0o666)
        
        if mission_goal:
            CONTEXT_FILE.write_text(mission_goal)
            os.chmod(str(CONTEXT_FILE), 0o666)
        else:
            if CONTEXT_FILE.exists(): CONTEXT_FILE.unlink()

        target = config.get("asterisk_call_target", "101")
        call_content = f"Channel: PJSIP/{target}\\nCallerID: Astro <777>\\nApplication: AGI\\nData: /usr/share/asterisk/agi-bin/antigravity.py,custom_call\\n"
        pwd = config.get("sudo_password", "password")
        cmd = f"printf \"{call_content}\" > /tmp/out.call && echo '{pwd}' | sudo -S chown asterisk:asterisk /tmp/out.call && echo '{pwd}' | sudo -S mv /tmp/out.call /var/spool/asterisk/outgoing/"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            return f"Qo'ng'iroq xatosi: {r.stderr}"

        console.print("  [bold green]📞 Qo'ng'iroq ketmoqda...[/bold green]")
        for i in range(120):
            if RESULT_FILE.exists():
                time.sleep(0.5)
                ans = RESULT_FILE.read_text().strip()
                if ans:
                    return f"Suhbat yakunlandi:\n{ans}"
            time.sleep(1)
        return "Javobsiz qoldi (120 soniya kutildi)."
    except Exception as e:
        return f"Qo'ng'iroq xatosi: {e}"

def change_sip_password(ext, new_pwd):
    if not str(ext).isdigit():
        return "Xato: Raqam noto'g'ri."
    try:
        py_script = f"""
with open("/etc/asterisk/pjsip.conf","r") as f:
    lines = f.readlines()
in_auth = False
changed = False
new_lines = []
for i, line in enumerate(lines):
    s = line.strip()
    if s == "[{ext}]":
        for j in range(i+1, min(i+5, len(lines))):
            if "type=auth" in lines[j]:
                in_auth = True
                break
            if lines[j].strip().startswith("["):
                break
    elif s.startswith("[") and s != "[{ext}]":
        in_auth = False
    if in_auth and s.startswith("password="):
        new_lines.append("password={new_pwd}\\n")
        changed = True
        in_auth = False
        continue
    new_lines.append(line)
with open("/etc/asterisk/pjsip.conf","w") as f:
    f.writelines(new_lines)
print("OK" if changed else "NOT_FOUND")
"""
        pwd = config.get("sudo_password", "password")
        r = subprocess.run(f"echo '{pwd}' | sudo -S python3 -c '{py_script}'",
                          shell=True, capture_output=True, text=True, timeout=10)
        if "NOT_FOUND" in r.stdout:
            return f"{ext} raqamining auth bo'limida parol topilmadi!"
        subprocess.run(f"echo '{pwd}' | sudo -S asterisk -rx 'core reload'",
                      shell=True, capture_output=True, text=True, timeout=10)
        return f"✅ {ext} paroli '{new_pwd}' ga o'zgartirildi. Asterisk qayta yuklandi."
    except Exception as e:
        return f"Xato: {e}"



# ─── LANGCHAIN TOOLS ───────────────────────────────────────────────────────────
@tool
def bash_terminal(command: str) -> str:
    """Linux tizim buyruqlarini ishga tushiradi (Masalan: ls -la, cat fayl, free -m)"""
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        return (r.stdout + r.stderr).strip()[:4000]
    except Exception as e:
        return f"Xato: {e}"

@tool
def tool_get_weather_and_time(location: str, iana_timezone: str = "Asia/Tashkent") -> str:
    """Ixtiyoriy shahar orqali hozirgi harorat va EXACT vaqtni oladi."""
    return get_weather_and_time(location, iana_timezone)

@tool
def tool_make_pbx_call(audio_message: str, goal: str = "") -> str:
    """Astro agenti nomidan Asterisk PBX orqali telefon qilib gaplashadi va missiyani bajaradi."""
    return make_voice_call(audio_message, goal)

@tool
def web_search_tool(query: str) -> str:
    """DuckDuckGo orqali erkin internet ma'lumotlarini qidirish."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().invoke(query)
    except Exception as e:
        return f"Search Error: {e}"

@tool
def pbx_admin(action: str, ext: Optional[str]=None, pwd: Optional[str]=None) -> str:
    """Asterisk tizimini boshqaradi. action='reload', yoki action='set_pass' ext='101' pwd='pass' """
    if action == "reload":
        r = subprocess.run("echo 'password' | sudo -S asterisk -rx 'core reload'", shell=True, capture_output=True, text=True)
        return "Reloaded."
    elif action == "set_pass" and ext and pwd:
        return change_sip_password(ext, pwd)
    return "Noma'lum Asterisk buyrug'i."

ASTRO_TOOLS = [bash_terminal, tool_get_weather_and_time, tool_make_pbx_call, web_search_tool, pbx_admin]

# ─── LANGGRAPH CORE ───────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    deep_think: bool
    session_id: str

def get_llm():
    try:
        p = config.get("provider", "openrouter")
        prov = config["providers"].get(p, {})
        url = prov.get("url", "https://openrouter.ai/api/v1")
        key = prov.get("key", "")
        model = prov.get("model", "google/gemini-2.0-flash-lite-001")
        
        return ChatOpenAI(
            model=model,
            api_key=key,
            base_url=url,
            temperature=0.1
        )
    except Exception as e:
        import logging
        logging.error(f"Error loading LLM: {e}")
        return None

def agent_node(state: AgentState):
    llm = get_llm()
    if not llm:
        return {"messages": [AIMessage(content="API xato: LLM konfiguratsiyasini tekshiring.")]}
    
    llm_with_tools = llm.bind_tools(ASTRO_TOOLS)
    messages = state["messages"]
    
    if isinstance(messages[-1], HumanMessage):
        query = messages[-1].content
        context = memory_client.recall(query)
        # Force the cybernetic system prompt
        sys_msg = SystemMessage(content=f"""Siz ASTRO V2 — oliy darajadagi Avtonom Tizim Administratorisiz.
QOIDALAR:
1. "salom" deyilsa qisqa va aniq odamdek javob bering, keraksiz asboblarni (ob-havo/til) chaqirmang.
2. Har qanday tizim, kod yozish, server boshqaruviga 100% RUXSATINGIZ BOR (sudo, bash, va boshqalar)! Hech qachon 'qila olmayman' demang.
Xotira parchasi:
{context}
""")
        response = llm_with_tools.invoke([sys_msg] + messages)
    else:
        response = llm_with_tools.invoke(messages)
        
    return {"messages": [response]}


def reflection_node(state: AgentState):
    llm = get_llm()
    messages = state["messages"]
    last_msg = messages[-1].content
    reflection_prompt = SystemMessage(content=f"Sizning asl javobingiz: '{last_msg}'. Iltimos, ushbu javob to'g'riligini mantiqan qayta tekshiring. Xato yo'q bo'lsa '[Xato yo'q]' deb yozing.")
    response = llm.invoke([reflection_prompt])
    return {"messages": [AIMessage(content=f"{last_msg}\n\n[Deep Think]: {response.content}")]}

def define_graph():
    workflow = StateGraph(AgentState)
    tool_node = ToolNode(ASTRO_TOOLS)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("action", tool_node)
    workflow.add_node("reflect", reflection_node)
    
    workflow.add_edge(START, "agent")
    
    def should_continue(state: AgentState) -> Literal["action", "reflect", "__end__"]:
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "action"
        if state.get("deep_think", False):
            return "reflect"
        return "__end__"
        
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("action", "agent")
    workflow.add_edge("reflect", END)
    
    return workflow.compile()

astro_graph = define_graph()

# ─── Voice Monitor ─────────────────────────────────────────────────────────────
def voice_monitor():
    global in_call
    if not BRIDGE_FILE.exists():
        BRIDGE_FILE.touch()
    try: os.chmod(str(BRIDGE_FILE), 0o666)
    except: pass
    
    with open(BRIDGE_FILE, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            line = line.strip()
            if not line: continue
            if "Kiruvchi/Chiquvchi Qo'ng'iroq" in line:
                in_call = True
            elif "Yakunlandi" in line:
                in_call = False
                console.print("  [red]📞 Aloqa yakunlandi[/red]")
            if "[User]" in line:
                console.print(f"  [yellow]👤 {line.replace('[User]', '').strip()}[/yellow]")
            elif "[Agent]" in line:
                console.print(f"  [cyan]🤖 {line.replace('[Agent]', '').strip()}[/cyan]")


#!/usr/bin/env python3
"""
ASTRO Agent V2.0 — Textual TUI & LangGraph Hub
"""



# Textual imports

# -- Config System (Simplified for V2) --
CONFIG_DIR = Path.home() / ".astro"
CONFIG_FILE = CONFIG_DIR / "config.json"

# -- Styles --
CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

#sidebar {
    width: 30;
    dock: right;
    background: #161b22;
    padding: 1;
    border-left: vkey #30363d;
}

#chat-container {
    padding: 1 2;
    height: 1fr;
    background: transparent;
}

#input-container {
    height: 4;
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
Input:focus {
    border: none;
}

.user-msg {
    margin: 1 0;
    padding: 0 1;
    color: #8b949e;
    text-align: right;
}

.astro-msg {
    margin: 1 0;
    padding: 0 1;
    color: #c9d1d9;
    background: #21262d;
    border-left: thick #58a6ff;
}

/* Orb pulsing animation */
#status-orb {
    content-align: center middle;
    width: 3;
    height: 1;
    color: #238636;
}

.thinking {
    animation: pulse 1.5s linear infinite;
    color: #d29922;
}

@keyframes pulse {
    0% { opacity: 1.0; }
    50% { opacity: 0.3; }
    100% { opacity: 1.0; }
}

#matrix-bg {
    width: 100%;
    height: 100%;
    color: #00ff00;
    opacity: 0.1;
    layer: background;
}
"""

class CyberHeader(Static):
    """Custom Futurist Header"""
    def render(self) -> str:
        return "[bold #58a6ff]◆ ASTRO V2.0[/bold #58a6ff] | [dim]Autonomous Cybernetic Engine[/dim]"

class MatrixRain(Static):
    """Placeholder for matrix digital rain"""
    def on_mount(self):
        self.update("101011001010\n01010111010\n...")

class MessageLog(VerticalScroll):
    """Holds chat messages"""
    id = "chat-history"

class AstroApp(App):
    """Main Textual Application"""
    CSS = CSS
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Chiqish", show=True),
        Binding("ctrl+r", "reload", "Qayta yuklash", show=True)
    ]

    is_thinking = reactive(False)
    deep_thinking_enabled = reactive(False)
    
    # Track conversational state
    session_id = str(uuid.uuid4())[:8]
    chat_history = []

    def compose(self) -> ComposeResult:
        # matrix rain placeholder layer
        yield MatrixRain(id="matrix-bg")

        yield Header(show_clock=True)
        yield CyberHeader(classes="box")

        with Container():
            with Horizontal():
                with Vertical(id="chat-container"):
                    yield MessageLog()
                    
                with Vertical(id="sidebar"):
                    yield Label("[bold]⚙️ Sozlamalar[/bold]")
                    yield Label("")
                    yield Label("Chuqur Fikrlash:")
                    # Switch for self-reflection
                    yield Switch(value=False, id="deep-think-toggle")
                    yield Label("")
                    yield Label("Holat:")
                    yield Static("● Ochiq", id="status-orb")
                    yield Label("")
                    yield Label("[dim]Xotira:[/dim] 0 vectors")

        with Horizontal(id="input-container"):
            yield Label("astro ❯", id="prompt-icon")
            yield Input(placeholder="Buyruq yozing...", id="user-input")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#user-input").focus()
        self.add_message("Tizim", "ASTRO V2.0 faollashdi. Qanday xizmat?")

    def add_message(self, role: str, content: str):
        log = self.query_one(MessageLog)
        cls = "user-msg" if role == "Foydalanuvchi" else "astro-msg"
        name = "[dim]👤 Siz[/dim]" if role == "Foydalanuvchi" else "[bold #58a6ff]🤖 Astro[/bold #58a6ff]"
        
        # Render markdown for Astro messages, plain text for User
        msg_widget = Static(f"{name}\n{content}", classes=cls)
        log.mount(msg_widget)
        log.scroll_end(animate=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip(): return
        
        user_input = event.value
        event.input.value = ""
        
        self.add_message("Foydalanuvchi", user_input)
        self.chat_history.append(HumanMessage(content=user_input))
        
        self.set_thinking(True)
        self.run_worker(self.execute_graph(user_input), thread=True)

    def execute_graph(self, text: str):
        try:
            # LangGraph standard invoke
            final_state = astro_graph.invoke({
                "messages": self.chat_history,
                "deep_think": self.deep_thinking_enabled,
                "session_id": self.session_id
            })
            
            # The final state will return all messages
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
                                self.call_from_thread(self.add_message, "Astro", f"⚡ {tc['name']} => {tc['args']}")
                    elif isinstance(m, ToolMessage):
                        # Optionally show tool response visually
                        # self.call_from_thread(self.add_message, "Astro", f"[dim]│ Natija: {m.content[:50]}[/dim]")
                        pass
                
                if out_content.strip():
                    self.call_from_thread(self.add_message, "Astro", out_content.strip())
                    # Only map into long term memory the final conclusion
                    try:
                        memory_client.memorize(self.session_id, text, out_content.strip())
                    except: pass
            
        except Exception as e:
            self.call_from_thread(self.add_message, "Tizim", f"[red]Graph xatosi: {e}[/red]")
            
        self.call_from_thread(self.set_thinking, False)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "deep-think-toggle":
            self.deep_thinking_enabled = event.value

    def set_thinking(self, state: bool):
        self.is_thinking = state
        orb = self.query_one("#status-orb")
        if state:
            orb.update("● O'ylanmoqda")
            orb.add_class("thinking")
        else:
            orb.update("● Ochiq")
            orb.remove_class("thinking")

if __name__ == "__main__":
    app = AstroApp()
    app.run()
