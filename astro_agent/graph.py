import os, json
from pathlib import Path
from typing import Annotated, Sequence, TypedDict, Literal

# LangChain / LangGraph imports
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Tools & Memory
from astro_agent.tools import ASTRO_TOOLS
from astro_agent.memory import memory_client

# Define State Structure
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    deep_think: bool
    session_id: str

# Configuration loader
def get_llm():
    from langchain_openai import ChatOpenAI
    
    cfg_path = Path.home() / ".astro" / "config.json"
    if not cfg_path.exists():
        return None
    try:
        cfg = json.loads(cfg_path.read_text())
        p = cfg.get("provider", "openrouter")
        prov = cfg["providers"].get(p, {})
        url = prov.get("url", "https://openrouter.ai/api/v1")
        key = prov.get("key", "")
        model = prov.get("model", "google/gemini-2.0-flash-lite-001")
        
        # We use ChatOpenAI because it is fully OpenAI format compatible (which OpenRouter uses)
        return ChatOpenAI(
            model=model,
            api_key=key,
            base_url=url,
            temperature=0.1
        )
    except Exception as e:
        print(f"Error loading LLM: {e}")
        return None

def agent_node(state: AgentState):
    llm = get_llm()
    if not llm:
        return {"messages": [AIMessage(content="API xato: LLM konfiguratsiyasini tekshiring.")]}
    
    llm_with_tools = llm.bind_tools(ASTRO_TOOLS)
    
    # Check if we should inject memory into the prompt
    messages = state["messages"]
    
    # Simple context injection: if this is a human message directly to agent, pull memory
    if isinstance(messages[-1], HumanMessage):
        query = messages[-1].content
        context = memory_client.recall(query)
        if context:
            # We don't overwrite history, we just temporarily inject it into the LLM system prompt
            sys_msg = SystemMessage(content=f"Siz ASTRO V2 Agentsiz. Xotira parchasi:\n{context}\n\nYuqoridagi kontekstdan foydalaning.")
            response = llm_with_tools.invoke([sys_msg] + messages)
        else:
            response = llm_with_tools.invoke(messages)
    else:
        response = llm_with_tools.invoke(messages)
        
    return {"messages": [response]}


def reflection_node(state: AgentState):
    """If deep thinking is on, the agent reviews its own response."""
    llm = get_llm()
    messages = state["messages"]
    last_msg = messages[-1].content
    
    reflection_prompt = SystemMessage(content=f"""Sizning asl javobingiz: '{last_msg}'. 
Iltimos, ushbu javob to'g'riligini mantiqan qayta tekshiring, xato bormi qidiring. Ekranga "[Self-Reflection] Xato topilmadi" deb xulosa chiqaring yoki yangilangan javobni yozing.""")
    
    response = llm.invoke([reflection_prompt])
    # Replace the last message with the reflection thought
    return {"messages": [AIMessage(content=f"{last_msg}\n\n[Deep Think]: {response.content}")]}

def define_graph():
    workflow = StateGraph(AgentState)
    
    tool_node = ToolNode(ASTRO_TOOLS)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("action", tool_node)
    workflow.add_node("reflect", reflection_node)
    
    workflow.add_edge(START, "agent")
    
    # Conditional routing: Action vs End/Reflect
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

# External accessor
astro_graph = define_graph()
