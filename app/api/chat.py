

import json
import logging
import re
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Message, Session as DBSession
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceReference,
    NoteResponse,
)
from app.core.llm_client import llm_client
from app.tools.note_tools import (
    TOOL_DEFINITIONS,
    save_note_handler,
    list_notes_handler,
    delete_note_handler,
    summarize_session_handler,
)
from app.rag.retriever import retriever
from app.rag.rewriter import analyze_and_rewrite_query


logger = logging.getLogger("askly.chat")

router = APIRouter(tags=["Chat & Notes"])


# ================================================================
# CONSTANTS & PATTERNS
# ================================================================

FALLBACK_ANSWER = (
    "I couldn't generate an answer right now. Please try the question again."
)

TOOL_ACTION_PATTERNS = [
    r"\bsave\s+(?:a\s+)?note\b",
    r"\brecord\s+(?:a\s+)?note\b",
    r"\bcreate\s+(?:a\s+)?note\b",
    r"\bremember\s+(?:this|that)\b",

    r"\blist\s+(?:my\s+)?notes?\b",
    r"\bshow\s+(?:my\s+)?notes?\b",

    r"\bdelete\s+(?:the\s+)?note\b",
    r"\bremove\s+(?:the\s+)?note\b",

    r"\bsummarize\b",
    r"\bsummary\b",
    r"\bwhat did we talk about\b",
    r"\bchat history\b",

    r"\bcompare\s+.+\s+(?:and|vs\.?|versus)\s+.+\b",
]


# ================================================================
# GENERIC OBJECT HELPERS
# ================================================================

def _get(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _extract_content(response: Any) -> str:
    if response is None:
        return ""

    content = _get(response, "content")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)

            if isinstance(text, str):
                parts.append(text)

        return "\n".join(parts).strip()

    if content is not None:
        return str(content).strip()

    return ""


def _extract_tool_calls(response: Any) -> list:
    return list(
        _get(response, "tool_calls") or []
    )


def _safe_json_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str) or not raw.strip():
        return {}

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}

    return (
        parsed
        if isinstance(parsed, dict)
        else {}
    )


def _is_tool_action(message: str) -> bool:
    return any(
        re.search(
            pattern,
            message,
            re.IGNORECASE,
        )
        for pattern in TOOL_ACTION_PATTERNS
    )


def _is_unknown_answer(text: str) -> bool:
    normalized = " ".join(
        (text or "").lower().split()
    )

    phrases = [
        "i don't know based on the uploaded pdf",
        "i don't know based on the pdf",
        "i couldn't find reliable information",
        "i could not find reliable information",
        "i couldn't find information about this topic in the uploaded document",
        "i could not find information about this topic in the uploaded document",
        "the uploaded pdf does not contain",
        "the pdf does not contain",
        "not enough information in the provided context",
        "not enough information in the pdf",
    ]

    return any(
        phrase in normalized
        for phrase in phrases
    )


# ================================================================
# HYBRID RAG / GENERAL CHAT GENERATION
# ================================================================

def _generate_hybrid_answer(
    user_message: str,
    retrieved_context: str,
) -> Tuple[str, bool]:
    if retrieved_context.strip():
        system_prompt = (
            "You are Askly, a helpful assistant. "
            "First, try to answer the user's question using ONLY the provided PDF evidence. "
            "If the PDF evidence contains the answer, provide it clearly. "
            "If the PDF evidence does NOT contain the answer, reply with exact text: 'NOT_FOUND_IN_PDF'"
        ).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"PDF EVIDENCE:\n{retrieved_context}\n\nUSER QUESTION:\n{user_message}"}
        ]

        try:
            response = llm_client.call(messages=messages, temperature=0.0)
            answer = _extract_content(response)
            
            if answer and "NOT_FOUND_IN_PDF" not in answer and not _is_unknown_answer(answer):
                return answer.strip(), False
        except Exception:
            logger.exception("PDF-based generation failed, falling back to general chat.")

    general_system_prompt = (
        "You are Askly, a knowledgeable AI chatbot. "
        "The user's question could not be answered using the uploaded PDF document. "
        "Please provide a helpful, accurate, and comprehensive answer using your general knowledge."
    ).strip()

    general_messages = [
        {"role": "system", "content": general_system_prompt},
        {"role": "user", "content": user_message}
    ]

    try:
        response = llm_client.call(messages=general_messages, temperature=0.3)
        general_answer = _extract_content(response)
        
        if general_answer:
            return general_answer.strip() + "\n\n*(Note: This information is out of the uploaded PDF)*", True
    except Exception:
        logger.exception("General knowledge generation failed.")

    return "I couldn't generate an answer for this right now.", True


# ================================================================
# SESSION SUMMARY
# ================================================================

def _run_summary(
    db: Session,
    session_id: str,
) -> str:
    try:
        result = summarize_session_handler(db, session_id)
    except Exception:
        return "I couldn't read the conversation history right now."

    if not isinstance(result, dict):
        return "I couldn't generate the session summary right now."

    history = result.get("raw_history", "")

    if not history:
        return "There is no conversation history recorded for this session yet."

    messages = [
        {
            "role": "system",
            "content": "Summarize ONLY the supplied conversation log. Return a concise bullet-point summary.",
        },
        {
            "role": "user",
            "content": f"Conversation log:\n{history}",
        },
    ]

    try:
        response = llm_client.call(messages=messages, temperature=0.0)
        return _extract_content(response) or "I couldn't generate the session summary right now."
    except Exception:
        return "I couldn't generate the session summary right now."


# ================================================================
# TOOL EXECUTION & KEYWORD FALLBACKS
# ================================================================

def _execute_tool_call(
    db: Session,
    session_id: str,
    user_message: str,
    function_name: str,
    args: dict,
) -> Tuple[str, Optional[int]]:

    if function_name == "save_note":
        title = str(args.get("title") or "Untitled").strip() or "Untitled"
        content = str(args.get("content") or "").strip() or user_message.strip()
        tags = str(args.get("tags") or "").strip()

        result = save_note_handler(db, session_id, title, content, tags)
        if result.get("status") != "success":
            return result.get("message", "Could not save the note."), None

        note_id = result.get("saved_note_id")
        return f"Note saved successfully with ID #{note_id}.\n\n**Title:** {title}\n**Content:** {content}", note_id

    if function_name == "list_notes":
        notes = list_notes_handler(db, session_id)
        if not notes:
            return "You have no saved notes in this session.", None

        notes_text = "\n".join(f"- **#{note['id']} {note['title']}**: {note['content']}" for note in notes)
        return f"Here are your saved notes:\n{notes_text}", None

    if function_name == "delete_note":
        try:
            note_id = int(args.get("note_id"))
        except (TypeError, ValueError):
            return "Please provide a valid note ID, for example: **Delete note #3**.", None

        result = delete_note_handler(db, session_id, note_id)
        return result.get("message", f"Note #{note_id} processed."), None

    if function_name == "summarize_session":
        return _run_summary(db, session_id), None

    if function_name == "compare_concepts":
        concept_a = str(args.get("concept_a") or "").strip()
        concept_b = str(args.get("concept_b") or "").strip()

        if not concept_a or not concept_b:
            return "Please provide both concepts to compare.", None

        try:
            docs_a = retriever.search(query=concept_a, top_k=3) or []
            docs_b = retriever.search(query=concept_b, top_k=3) or []
        except Exception:
            docs_a, docs_b = [], []

        context_a = "\n".join(d.get("content", "") for d in docs_a if d.get("content"))
        context_b = "\n".join(d.get("content", "") for d in docs_b if d.get("content"))

        comparison_prompt = [
            {
                "role": "system",
                "content": "Compare two concepts using the supplied PDF contexts or general knowledge if PDF context is missing.",
            },
            {
                "role": "user",
                "content": f"Concept A: {concept_a}\nContext A:\n{context_a}\n\nConcept B: {concept_b}\nContext B:\n{context_b}",
            },
        ]

        try:
            response = llm_client.call(messages=comparison_prompt, temperature=0.0)
            return _extract_content(response) or "I couldn't compare those concepts right now.", None
        except Exception:
            return "I couldn't compare those concepts right now.", None

    return "I couldn't process that action.", None


def _keyword_fallback_action(
    db: Session,
    session_id: str,
    request_message: str,
) -> Tuple[str, Optional[int]]:
    msg = request_message.lower()

    if re.search(r"\b(summarize|summary)\b", msg) or "what did we talk about" in msg or "chat history" in msg:
        return _run_summary(db, session_id), None

    if re.search(r"\b(delete|remove)\b", msg) and "note" in msg:
        match = re.search(r"(?:#|note\s*)?(\d+)\b", msg)
        if not match:
            return "Please provide the note ID, for example: **Delete note #3**.", None
        note_id = int(match.group(1))
        result = delete_note_handler(db, session_id, note_id)
        return result.get("message", "Note processed."), None

    if re.search(r"\b(list|show)\b", msg) and re.search(r"\bnotes?\b", msg):
        notes = list_notes_handler(db, session_id)
        if not notes:
            return "You have no saved notes in this session.", None
        notes_text = "\n".join(f"- **#{note['id']} {note['title']}**: {note['content']}" for note in notes)
        return f"Here are your saved notes:\n{notes_text}", None

    if re.search(r"\b(save|record|create|remember)\b", msg) and ("note" in msg or "this" in msg or "that" in msg):
        title_match = re.search(r"(?:titled|title(?:d)?\s+as)\s+['\"]([^'\"]+)['\"]", request_message, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Untitled Note"
        content = request_message

        result = save_note_handler(db, session_id, title, content)
        if result.get("status") != "success":
            return result.get("message", "Could not save note."), None
        note_id = result.get("saved_note_id")
        return f"Note saved successfully with ID #{note_id}.\n\n**Title:** {title}\n**Content:** {content}", note_id

    return "", None


# ================================================================
# CHAT ENDPOINT
# ================================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        user_message = (request.message or "").strip()

        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        session_obj = db.query(DBSession).filter(DBSession.id == request.session_id).first()
        if not session_obj:
            session_obj = DBSession(id=request.session_id)
            db.add(session_obj)
            db.commit()

        past_messages = (
            db.query(Message)
            .filter(Message.session_id == request.session_id)
            .order_by(Message.timestamp.desc())
            .limit(12)
            .all()
        )
        past_messages.reverse()

        history_text = "\n".join(f"{message.role}: {message.content}" for message in past_messages)

        db.add(Message(session_id=request.session_id, role="user", content=user_message))
        db.commit()

        # Safer query rewriter handling with explicit fallback
        try:
            rewritten = analyze_and_rewrite_query(user_message, history_text)
            if not isinstance(rewritten, dict):
                rewritten = {}
        except Exception:
            logger.exception("Query rewriting module encountered an error; proceeding with original message.")
            rewritten = {}

        intent = str(rewritten.get("intent") or "RAG_SEARCH").upper()
        rewritten_query = str(rewritten.get("rewritten_query") or user_message).strip() or user_message

        if _is_tool_action(user_message):
            intent = "TOOL_ACTION"

        if intent == "TOOL_ACTION":
            tool_messages = [
                {
                    "role": "system",
                    "content": "You are Askly's action router. Use a tool only when the user explicitly asks to save, list, delete, summarize, or compare.",
                },
                {"role": "user", "content": user_message},
            ]

            response_msg = None
            try:
                response_msg = llm_client.call_with_tools(messages=tool_messages, tools=TOOL_DEFINITIONS, temperature=0.0)
            except Exception:
                pass

            final_answer = ""
            saved_note_id = None

            for tool_call in _extract_tool_calls(response_msg):
                function_obj = _get(tool_call, "function")
                function_name = str(_get(function_obj, "name", "") or "")
                args = _safe_json_args(_get(function_obj, "arguments"))

                try:
                    answer_text, note_id = _execute_tool_call(db, request.session_id, user_message, function_name, args)
                except Exception:
                    answer_text, note_id = "I couldn't complete that action due to an internal error.", None

                if answer_text:
                    final_answer = answer_text
                if note_id is not None:
                    saved_note_id = note_id

            if not final_answer:
                final_answer, fallback_note_id = _keyword_fallback_action(db, request.session_id, user_message)
                if saved_note_id is None:
                    saved_note_id = fallback_note_id

            if not final_answer.strip():
                final_answer = FALLBACK_ANSWER

            db.add(Message(session_id=request.session_id, role="assistant", content=final_answer))
            db.commit()

            return ChatResponse(
                answer=final_answer,
                sources=[],
                retrieved_context=None,
                saved_note_id=saved_note_id,
            )

        try:
            docs = retriever.search(query=rewritten_query, top_k=4) or []
        except Exception:
            docs = []

        useful_docs = [
            doc for doc in docs
            if isinstance(doc, dict) and str(doc.get("content", "")).strip()
        ]

        context_parts = []
        for index, doc in enumerate(useful_docs, start=1):
            source = doc.get("source", "uploaded document")
            content = str(doc.get("content", "")).strip()
            context_parts.append(f"[PDF SOURCE {index}: {source}]\n{content}")

        retrieved_context = "\n\n".join(context_parts)

        sources = [
            SourceReference(
                document=doc.get("source", "uploaded document"),
                snippet=str(doc.get("content", ""))[:300],
            )
            for doc in useful_docs
        ]

        final_answer, is_out_of_pdf = _generate_hybrid_answer(
            user_message=rewritten_query,
            retrieved_context=retrieved_context,
        )

        if is_out_of_pdf:
            sources = []
            retrieved_context = None

        db.add(Message(session_id=request.session_id, role="assistant", content=final_answer))
        db.commit()

        return ChatResponse(
            answer=final_answer,
            sources=sources,
            retrieved_context=retrieved_context,
            saved_note_id=None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in /chat")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing the chat.") from exc


@router.get(
    "/notes",
    response_model=list[NoteResponse],
)
async def get_notes_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
):
    try:
        notes = list_notes_handler(db, session_id)
        return [
            NoteResponse(
                id=note["id"],
                session_id=session_id,
                title=note["title"],
                content=note["content"],
                tags=note.get("tags") or "",
            )
            for note in notes
        ]
    except Exception as exc:
        logger.exception("Failed to fetch notes.")
        raise HTTPException(status_code=500, detail="Could not fetch notes.") from exc
