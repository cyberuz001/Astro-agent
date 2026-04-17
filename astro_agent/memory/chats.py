"""
Chat session persistence manager.
Stores chat sessions as JSON files in ~/.astro/chats/
Each chat has: id, title (auto from first message), messages list, timestamp.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

CHATS_DIR = Path.home() / ".astro" / "chats"


def _ensure_dir():
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def list_chats() -> list[dict]:
    """Return list of chat metadata sorted by last_updated (newest first)."""
    _ensure_dir()
    chats = []
    for f in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            chats.append({
                "id": data.get("id", f.stem),
                "title": data.get("title", "Untitled"),
                "message_count": len(data.get("messages", [])),
                "last_updated": data.get("last_updated", 0),
            })
        except Exception:
            continue
    chats.sort(key=lambda x: x["last_updated"], reverse=True)
    return chats


def load_chat(chat_id: str) -> Optional[dict]:
    """Load full chat data by ID."""
    _ensure_dir()
    p = CHATS_DIR / f"{chat_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def save_chat(chat_id: str, title: str, messages: list[dict], session_id: str = ""):
    """Save/overwrite a chat session."""
    _ensure_dir()
    data = {
        "id": chat_id,
        "title": title,
        "session_id": session_id,
        "messages": messages,
        "last_updated": time.time(),
    }
    (CHATS_DIR / f"{chat_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2)
    )


def delete_chat(chat_id: str) -> bool:
    """Delete a chat by ID. Returns True if deleted."""
    _ensure_dir()
    p = CHATS_DIR / f"{chat_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False


def new_chat_id() -> str:
    return uuid.uuid4().hex[:8]


def messages_to_dicts(messages) -> list[dict]:
    """Convert LangChain message objects to serializable dicts."""
    result = []
    for m in messages:
        role = "human"
        if hasattr(m, "type"):
            role = m.type  # "human", "ai", "system", "tool"
        result.append({"role": role, "content": m.content})
    return result


def dicts_to_messages(dicts: list[dict]):
    """Convert dicts back to LangChain message objects."""
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    result = []
    for d in dicts:
        role = d.get("role", "human")
        content = d.get("content", "")
        if role == "human":
            result.append(HumanMessage(content=content))
        elif role == "ai":
            result.append(AIMessage(content=content))
        elif role == "system":
            result.append(SystemMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result
