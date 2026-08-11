from sqlalchemy.orm import Session
from app.db.models import SavedNote, Message

# ---------------------------------------------------------
# Python Tool Handlers
# ---------------------------------------------------------

def save_note_handler(db: Session, session_id: str, title: str, content: str, tags: str = "") -> dict:
    note = SavedNote(session_id=session_id, title=title, content=content, tags=tags)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"status": "success", "saved_note_id": note.id}

def list_notes_handler(db: Session, session_id: str) -> list:
    notes = db.query(SavedNote).filter(SavedNote.session_id == session_id).all()
    return [{"id": n.id, "title": n.title, "content": n.content, "tags": n.tags} for n in notes]

def delete_note_handler(db: Session, session_id: str, note_id: int) -> dict:
    note = db.query(SavedNote).filter(SavedNote.id == note_id, SavedNote.session_id == session_id).first()
    if not note:
        return {"status": "error", "message": f"Note #{note_id} not found."}
    db.delete(note)
    db.commit()
    return {"status": "success", "message": f"Note #{note_id} deleted successfully."}

def summarize_session_handler(db: Session, session_id: str) -> dict:
    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()
    if not messages:
        return {"status": "empty", "summary": "No previous conversation history found."}
    
    chat_log = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
    return {"status": "success", "total_messages": len(messages), "raw_history": chat_log}


# ---------------------------------------------------------
# JSON Schemas for Function Calling
# ---------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "CRITICAL: MUST be called whenever the user asks to save, record, or store a note, summary, or snippet into SQLite.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the note"},
                    "content": {"type": "string", "description": "Body text or content to save"},
                    "tags": {"type": "string", "description": "Optional comma-separated tags"}
                },
                "required": ["title", "content"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "Lists all user-saved notes for the active session. ONLY use when user explicitly requests to list or show saved notes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Deletes a specific note from SQLite using its note ID. ONLY use when user asks to delete a note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "The ID of the note to delete"}
                },
                "required": ["note_id"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_concepts",
            "description": "ONLY use when the user EXPLICITLY asks to compare two distinct concepts side-by-side using the word 'compare'. Do NOT use for general queries like 'what are its types'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_a": {"type": "string", "description": "First concept to compare"},
                    "concept_b": {"type": "string", "description": "Second concept to compare"}
                },
                "required": ["concept_a", "concept_b"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_session",
            "description": "CRITICAL: MUST be called whenever the user asks to summarize, recap, or review the discussion or conversation history of the current session.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_source_metadata",
            "description": "Inspects ChromaDB vector index to return names of all indexed files.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            "strict": True
        }
    }
]