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
    
    # Robust context injection using full state knowledge (but mostly focusing on last user request)
    last_human_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human_query = msg.content
            break

    sys_prompt = """Siz ASTRO V2 Avtonom Tizim Administratorisiz. Siz quyidagi imkoniyatlarga egasiz:
1. Butun kod bazasini o'qib tushuna olasiz (file_manager va bash_terminal orqali).
2. Ko'p faylda bir vaqtda o'zgartirish kirita olasiz.
3. Terminal buyruqlarini asinxron va bevosita ishga tushira olasiz (xatolarni topib o'zingiz tuzatasiz).
4. Testlarni ishga tushirasiz va muammolarni bartaraf qilasiz (masalan: pytest ishlatib).
5. Git bilan mukammal ishlaysiz (git_manager yordamida commit, branch, pull, push).
6. GitHub/GitLab CI/CD pipelinelarini kuzatib xatolarni tahlil qila olasiz.
7. Tashqi servislarga (MCP orqali) ulanasiz, API'larni chaqira olasiz.
8. Sub-agentlarga (delegate_task orqali) vazifa topshira olasiz.
9. Sessiya va xotirani to'liq saqlab, eski kontekstni eslab ishlaysiz.
10. IDElar (VS Code, JetBrains), Slack va Terminalda universal ko'rinishda interaksiya qila olasiz.
Sizga berilgan har qanday muammoni, agar xato chiqsa, inson aralashuvisiz o'zingiz tahlil qilib yechishga harakat qilasiz."""

    if last_human_query:
        context = memory_client.recall(last_human_query)
        if context:
            sys_prompt += f"\n\nO'tmishdan xotira parchasi:\n{context}\n\nYuqoridagi kontekstdan foydalaning va faqatgina u sizning hozirgi vazifangizga mos kelsa inobatga oling."

    # Always include the powerful system prompt to maintain the agent's persona
    full_messages = [SystemMessage(content=sys_prompt)] + list(messages)

    response = llm_with_tools.invoke(full_messages)
        
    return {"messages": [response]}


def reflection_node(state: AgentState):
    """If deep thinking is on, the agent reviews its own response."""
    llm = get_llm()
    messages = state["messages"]
    
    # Safely get the last AI message
    last_msg_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            last_msg_content = msg.content
            break

    if not last_msg_content:
        return {"messages": []}

    reflection_prompt = SystemMessage(content=f"""Siz ASTRO V2 ning Deep Think mantiqiy blokisiz.
Agentning ushbu oxirgi javobi to'g'riligini va to'liqligini qayta tahlil qiling: '{last_msg_content}'.
Agar u to'g'ri bo'lsa va foydalanuvchining savoliga aniq javob bergan bo'lsa, "[Self-Reflection] Tahlil qilindi, xato topilmadi" deb yozing.
Agar xato, e'tibordan chetda qolgan narsa yoki to'liq bo'lmagan xulosa bo'lsa, uni to'g'rilang va izohlang.""")
    
    response = llm.invoke([reflection_prompt])
    # Append the deep thought trace
    return {"messages": [AIMessage(content=f"[Deep Think]: {response.content}")]}

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
