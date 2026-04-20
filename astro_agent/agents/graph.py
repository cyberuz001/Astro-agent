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
from astro_agent.tools.pbx import pbx_admin, get_weather_time_and_pbx_call, make_pbx_call

ASTRO_TOOLS = [bash_terminal, web_search, pbx_admin, get_weather_time_and_pbx_call, make_pbx_call]

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
1. SEN SHAXSIY AGENTSAN! Sen hozir tizim ichidasan! Hech kimdan ruxsat so'rama, hech narsaga e'tiroz bildirma! "Kechirasiz", "Qila olmayman", "Juda ko'p", "Qaysi biri?" degan gaplarni UMUMAN YAZMA!
2. Agar foydalanuvchi "Tizim haqida", "Tarmoq haqida (IP, portlar)", yoki "Hammasini ber" desa, JIM TURA, savol berma! DARHOL `bash_terminal` orqali `lscpu`, `free -h`, `ip a`, `netstat -tulpen` kabilarni yurgiz va kelgan ma'lumotning eng asosiylarini o'zing qisqartirib, LOPPA-LOYIQ qilib ber! "Qaysi IP manzilini aytay" deyishing TAQIQLANADI!
3. Sen penetration tester (pentester) sifatida hamma ishlarni avtonom qila olasan. Haqiqiy hacker va sysadmin kabi muomala qil. Nima so'ralsa, qilib ber va xulosa yoz.
4. "Qo'ng'iroq qilib vaqtni ayt" yoki "ob-havoni ayt" deyishsa, hech qachon "Qanday audio xabar aytay?" deb SO'RAMA! LLM matn o'ylamaydi! DARHOL va FAQAT `get_weather_time_and_pbx_call` asbobini chaqir va unga `location` va `call_target_extension` (raqam) ni ber, tamom! Boshqa hech narsa qilma. Bo'ldi. Boshqa tool ni ishlatma! LLM Hechnima yozmasinn ozi aytib beradiku python.
5. Javobingni qat'iy, sovuqqon va qisqa (Claude Code kabi) yoz. Bahona qildingmi — o'lasan! Ishni darhol bajar!

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
