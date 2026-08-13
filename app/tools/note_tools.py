import logging

from sqlalchemy.orm import Session

from app.db.models import SavedNote, Message


logger = logging.getLogger("askly.note_tools")


def save_note_handler(
    db: Session,
    session_id: str,
    title: str,
    content: str,
    tags: str = "",
) -> dict:
    title = (title or "Untitled").strip() or "Untitled"
    content = (content or "").strip()
    tags = (tags or "").strip()

    if not content:
        return {
            "status": "error",
            "message": "Cannot save an empty note.",
            "saved_note_id": None,
        }

    try:
        note = SavedNote(
            session_id=session_id,
            title=title,
            content=content,
            tags=tags,
        )

        db.add(note)
        db.commit()
        db.refresh(note)

        return {
            "status": "success",
            "saved_note_id": note.id,
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to save note for session %s",
            session_id,
        )

        return {
            "status": "error",
            "message": "Could not save the note due to a database error.",
            "saved_note_id": None,
        }


def list_notes_handler(
    db: Session,
    session_id: str,
) -> list:
    try:
        notes = (
            db.query(SavedNote)
            .filter(SavedNote.session_id == session_id)
            .order_by(SavedNote.id.asc())
            .all()
        )

        return [
            {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "tags": note.tags or "",
            }
            for note in notes
        ]

    except Exception:
        logger.exception(
            "Failed to list notes for session %s",
            session_id,
        )
        return []


def delete_note_handler(
    db: Session,
    session_id: str,
    note_id: int,
) -> dict:
    try:
        note = (
            db.query(SavedNote)
            .filter(
                SavedNote.id == note_id,
                SavedNote.session_id == session_id,
            )
            .first()
        )

        if not note:
            return {
                "status": "error",
                "message": f"Note #{note_id} not found.",
            }

        db.delete(note)
        db.commit()

        return {
            "status": "success",
            "message": f"Note #{note_id} deleted successfully.",
        }

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to delete note #%s for session %s",
            note_id,
            session_id,
        )

        return {
            "status": "error",
            "message": (
                f"Could not delete note #{note_id} "
                "due to a database error."
            ),
        }


def summarize_session_handler(
    db: Session,
    session_id: str,
) -> dict:
    try:
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

        if not messages:
            return {
                "status": "empty",
                "raw_history": "",
            }

        # Exclude the very last incoming user message if it is requesting the summary itself
        if len(messages) > 1:
            last_content = (messages[-1].content or "").lower()
            if (
                "summarize" in last_content
                or "summary" in last_content
                or "what did we talk about" in last_content
            ):
                messages = messages[:-1]

        if not messages:
            return {
                "status": "empty",
                "raw_history": "",
            }

        chat_log = "\n".join(
            f"{message.role.upper()}: {message.content}"
            for message in messages
        )

        return {
            "status": "success",
            "raw_history": chat_log,
        }

    except Exception:
        logger.exception(
            "Failed to build session history for %s",
            session_id,
        )

        return {
            "status": "error",
            "raw_history": "",
        }


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": (
                "Saves a note to SQLite. Use only when the user explicitly "
                "asks to save, record, create, or remember a note."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the note.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The note content.",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Optional comma-separated tags.",
                    },
                },
                "required": ["title", "content"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": (
                "Lists all notes belonging to the current session. "
                "Use only when the user explicitly asks to list/show notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": (
                "Deletes one note by ID. Use only when the user explicitly "
                "asks to delete/remove a note."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "integer",
                        "description": "ID of the note to delete.",
                    },
                },
                "required": ["note_id"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_concepts",
            "description": (
                "Compares two concepts using information retrieved from "
                "the uploaded PDF."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_a": {"type": "string"},
                    "concept_b": {"type": "string"},
                },
                "required": ["concept_a", "concept_b"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_session",
            "description": (
                "Summarizes the current conversation session. Use only "
                "when the user explicitly asks to summarize the chat, "
                "conversation, or session."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]