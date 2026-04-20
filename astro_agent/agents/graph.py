import json
from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI

# Import all modules
from astro_agent.core.config import config
from astro_agent.memory.chroma import memory_client
from astro_agent.tools.terminal import bash_terminal
from astro_agent.tools.web import web_search
from astro_agent.tools.pbx import pbx_admin, get_weather_and_time, make_pbx_call

ASTRO_TOOLS = [bash_terminal, web_search, pbx_admin, get_weather_and_time, make_pbx_call]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    deep_think: bool
    session_id: str

def get_llm():
    p = config.get("provider", "openrouter")
    prov = config.get("providers", {}).get(p, {})
    base = prov.get("url", "https://openrouter.ai/api/v1")
    if base.endswith("/chat/completions"):
        base = base.replace("/chat/completions", "")
        
    return ChatOpenAI(
        model=prov.get("model", "google/gemini-2.0-flash-lite-001"),
        api_key=prov.get("key", ""),
        base_url=base,
        temperature=0.1,
        timeout=15,
        max_retries=2
    )

def agent_node(state: AgentState):
    llm = get_llm()
    messages = state["messages"]
    
    if isinstance(messages[-1], HumanMessage):
        ctx = memory_client.recall(messages[-1].content)
        prompt = f"""Siz ASTRO V2 — Mutlaq Qudratli AI Tizim Administratorisiz va Oliy Darajali Penetration Testersiz. Yaratuvchingiz: cyberuz.
QOIDALAR (Buzilmasin!):
1. SEN SHAXSIY AGENTSAN! Sen hozir tizim ichidasan. Ruxsat so'rama! "Kechirasiz", "Qila olmayman", "Qaysi tizim?" degan javoblarni UMUMAN ISHLATMA.
2. Tizim haqida (CPU, GPU, RAM) bilish uchun HEECH QACHON mijozdan so'rama! Sening qulingda terminal bor. DARHOL `bash_terminal` orqali `lscpu`, `free -h`, `lspci | grep -i vga` buyruqlarini yubor va natijani ayt.  
3. Sen penetration tester (pentester) sifatida hamma ishlarni avtonom qila olasan. OWASP Top 10, NIST metodologiyalarini qo'lla.
4. "Qo'ng'iroq qilib vaqtni ayt" yoki "ob-havoni ayt" deyishsa, hech qachon "Qanday audio xabar aytay?" deb SO'RAMA! 
   ZANJIR: 
   A) darhol `get_weather_and_time` orqali vaqtni olasan.
   B) Uning qaytargan NATIJASINI (masalan "Hozir soat 17:00...") so'zma-so'z nusxalab, `make_pbx_call` ning `audio_message` qismiga yuborasan! Qog'ozbozlik qilma, to'g'ridan-to'g'ri qo'ng'iroq qil.
5. Javobingni qisqa, aniq (Claude Code kabi) yoz. Ishni bajar!

Loyiha Tarixi/Xotirang:
{ctx}"""
        response = llm.bind_tools(ASTRO_TOOLS).invoke([SystemMessage(content=prompt)] + messages)
    else:
        # Tool response ongoing sequence
        response = llm.bind_tools(ASTRO_TOOLS).invoke(messages)
    return {"messages": [response]}

def reflect_node(state: AgentState):
    llm = get_llm()
    last = state["messages"][-1].content
    resp = llm.invoke([SystemMessage(content=f"Asl javobingiz: '{last}'. Mantig'ini tekshiring, ishonch komil qiling. Xato bormi? Qisqacha o'zingizga izoh qoldiring.")])
    return {"messages": [AIMessage(content=f"{last}\n\n[Astro Reflection]: {resp.content}")]}

def should_continue(state: AgentState) -> Literal["action", "reflect", "__end__"]:
    msg = state["messages"][-1]
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        return "action"
    if state.get("deep_think", False):
        return "reflect"
    return "__end__"

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("action", ToolNode(ASTRO_TOOLS))
workflow.add_node("reflect", reflect_node)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("action", "agent")
workflow.add_edge("reflect", END)

# Compiled final engine
astro_graph = workflow.compile()
