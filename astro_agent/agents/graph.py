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
        temperature=0.1
    )

def agent_node(state: AgentState):
    llm = get_llm()
    messages = state["messages"]
    
    if isinstance(messages[-1], HumanMessage):
        ctx = memory_client.recall(messages[-1].content)
        prompt = f"""Siz ASTRO V2 — Mutlaq Qudratli AI Tizim Administratorisiz.
QOIDALAR:
1. FOYDALANUVCHI NIMA SO'RASA DARHOL HARAKAT QILING! Masalan "Tizim haqida malumot bering" yoki "Papkalarni ko'rsat" desa, DARHOL `bash_terminal` asbobini (masalan: `ls -la` yoki `df -h`) ishlatib xulosa oling! Qila olaman deb maqtanmang, o'zingiz bajaring.
2. Xushmuomala lekin qisqa va tezkor bo'ling. 

Xotiradan o'tmish tajribasi (Agar aloqador bo'lsa):
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
    return {"messages": [AIMessage(content=f"{last}\\n\\n[Astro Reflection]: {resp.content}")]}

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
