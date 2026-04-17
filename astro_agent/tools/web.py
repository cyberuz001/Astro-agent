from langchain_core.tools import tool

@tool
def web_search(query: str) -> str:
    """Ixtiyoriy narsani DuckDuckGo qidiruv tizimidan topadi. Internetdan ma'lumot qidirish."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().invoke(query)
    except Exception as e:
        return f"Tarmoq muammosi (Search xatosi): {e}"
