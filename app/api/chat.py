import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Message, Session as DBSession
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference, NoteResponse
from app.core.llm_client import llm_client
from app.tools.note_tools import (
    TOOL_DEFINITIONS, 
    save_note_handler, 
    list_notes_handler,
    delete_note_handler,
    summarize_session_handler
)
from app.rag.retriever import retriever
from app.rag.rewriter import analyze_and_rewrite_query

router = APIRouter(tags=["Chat & Notes"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        # 1. Manage session record in SQLite
        session_obj = db.query(DBSession).filter(DBSession.id == request.session_id).first()
        if not session_obj:
            session_obj = DBSession(id=request.session_id)
            db.add(session_obj)
            db.commit()

        # 2. Extract recent past history for query rewriting
        past = db.query(Message).filter(Message.session_id == request.session_id).order_by(Message.timestamp.desc()).limit(6).all()
        history_text = "\n".join([f"{m.role}: {m.content}" for m in reversed(past)])

        # Save user message to database
        db.add(Message(session_id=request.session_id, role="user", content=request.message))
        db.commit()

        # 3. Rewrite query (analyzes follow-ups using past history and outputs validated JSON)
        rewritten = analyze_and_rewrite_query(request.message, history_text)
        intent = rewritten.get("intent", "RAG_SEARCH")
        rewritten_query = rewritten.get("rewritten_query", request.message)

        # Force intent override if message matches explicit tool operations
        msg_lower = request.message.lower()
        tool_keywords = ["save note", "save a note", "record note", "create note", "list notes", "show notes", "delete note", "summarize session", "summarize what"]
        if any(kw in msg_lower for kw in tool_keywords):
            intent = "TOOL_ACTION"

        retrieved_context = None
        sources = []
        saved_note_id = None

        # Path 1: Vector Document Search via ChromaDB
        if intent == "RAG_SEARCH":
            docs = retriever.search(query=rewritten_query, top_k=2)
            if docs:
                retrieved_context = "\n\n".join([f"Source ({d['source']}): {d['content']}" for d in docs])
                sources = [SourceReference(document=d["source"], snippet=d["content"][:100]) for d in docs]

        # Construct System Prompt with strict Grounding Rules
        sys_prompt = (
            "You are Askly, an intelligent research assistant.\n\n"
            "STRICT GROUNDING RULES:\n"
            "1. Answer the user query strictly using the retrieved context provided below.\n"
            "2. If the user's question asks about topics completely absent from the retrieved context (e.g., general science definitions like 'what is BIOLOGY' or external facts not in the context), explicitly state: "
            "'I couldn't find information about this topic in the uploaded document.'\n"
            "3. Do NOT make up answers using outside knowledge if context is provided but doesn't contain the answer.\n"
            "4. If the user commands an explicit action like saving, listing, or deleting notes, or summarizing, execute the respective tool call.\n"
            "5. DO NOT output XML or function tags like <function> in text output."
        )

        if retrieved_context:
            sys_prompt += f"\n\nRetrieved Context:\n{retrieved_context}"

        messages_payload = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": request.message}
        ]

        # Call LLM with tool definitions, handling potential Groq tool-use errors gracefully
        try:
            response_msg = llm_client.call_with_tools(messages=messages_payload, tools=TOOL_DEFINITIONS)
        except Exception:
            # Fallback to direct chat mode if Groq tool syntax validation fails
            response_msg = llm_client.call_with_tools(messages=messages_payload, tools=[])

        final_answer = ""

        # Path A: Standard Function/Tool Calling Logic
        if response_msg.tool_calls:
            for tool_call in response_msg.tool_calls:
                func_name = tool_call.function.name
                
                try:
                    raw_args = json.loads(tool_call.function.arguments or "{}")
                    args = raw_args[0] if isinstance(raw_args, list) and len(raw_args) > 0 else raw_args
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}

                # Tool 1: Save Note
                if func_name == "save_note":
                    title = args.get("title", "Untitled")
                    content = args.get("content", "")
                    tags = args.get("tags", "")
                    
                    res = save_note_handler(db, request.session_id, title, content, tags)
                    saved_note_id = res.get("saved_note_id")
                    final_answer = f"Note saved successfully with ID #{saved_note_id}."

                # Tool 2: List Notes
                elif func_name == "list_notes":
                    notes = list_notes_handler(db, request.session_id)
                    final_answer = f"Saved notes: {json.dumps(notes)}"

                # Tool 3: Delete Note
                elif func_name == "delete_note":
                    note_id = args.get("note_id", 0)
                    res = delete_note_handler(db, request.session_id, int(note_id))
                    final_answer = res.get("message")

                # Tool 4: Compare Concepts
                elif func_name == "compare_concepts":
                    concept_a = args.get("concept_a", "")
                    concept_b = args.get("concept_b", "")
                    
                    docs_a = retriever.search(query=concept_a, top_k=2) if concept_a else []
                    docs_b = retriever.search(query=concept_b, top_k=2) if concept_b else []
                    
                    context_a_str = "\n".join([d['content'] for d in docs_a]) if docs_a else "No relevant context found."
                    context_b_str = "\n".join([d['content'] for d in docs_b]) if docs_b else "No relevant context found."
                    
                    final_answer = (
                        f"### Comparison: {concept_a} vs {concept_b}\n\n"
                        f"**{concept_a}:**\n{context_a_str}\n\n"
                        f"**{concept_b}:**\n{context_b_str}"
                    )

                # Tool 5: Summarize Session
                elif func_name == "summarize_session":
                    summary_res = summarize_session_handler(db, request.session_id)
                    history_data = summary_res.get("raw_history", "")
                    
                    if not history_data or summary_res.get("status") == "empty":
                        final_answer = "There is no previous conversation history recorded for this session yet."
                    else:
                        summary_prompt = [
                            {"role": "system", "content": "You are a research assistant. Summarize the following session history clearly into concise bullet points detailing key topics discussed and actions taken."},
                            {"role": "user", "content": f"Conversation Log:\n{history_data}"}
                        ]
                        summary_response = llm_client.call_with_tools(messages=summary_prompt, tools=[])
                        final_answer = summary_response.content or "Could not generate session summary."

                # Tool 6: Get Source Metadata
                elif func_name == "get_source_metadata":
                    final_answer = "Knowledge base index includes active files under `./data/` directory (e.g., sample.pdf)."

        # Path B: Deterministic Fallback Guard (If LLM skips tool_calls and returns plain text)
        else:
            if intent == "TOOL_ACTION" and "save" in msg_lower:
                title_match = re.search(r"titled\s+['\"]?([^'\"]+)['\"]?", request.message, re.IGNORECASE)
                content_match = re.search(r"content\s+['\"]?([^'\"]+)['\"]?", request.message, re.IGNORECASE)
                
                extracted_title = title_match.group(1).rstrip('.') if title_match else "Saved Note"
                extracted_content = content_match.group(1).rstrip('.') if content_match else request.message
                
                res = save_note_handler(db, request.session_id, extracted_title, extracted_content, "")
                saved_note_id = res.get("saved_note_id")
                final_answer = f"Note saved successfully with ID #{saved_note_id}."
            else:
                content = response_msg.content or ""
                if "<function" in content:
                    content = content.split("<function")[0].strip()
                final_answer = content or "No response generated."

                # Post-check: If LLM explicitly indicates out-of-context topic, clear sources list
                if "couldn't find information" in final_answer.lower() or "not in the uploaded document" in final_answer.lower():
                    sources = []

        # Save assistant answer to database
        db.add(Message(session_id=request.session_id, role="assistant", content=final_answer))
        db.commit()

        return ChatResponse(
            answer=final_answer,
            sources=sources,
            retrieved_context=retrieved_context if sources else None,
            saved_note_id=saved_note_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notes", response_model=list[NoteResponse])
async def get_notes_endpoint(session_id: str, db: Session = Depends(get_db)):
    """Secondary Endpoint: Fetch all notes directly without LLM calling."""
    try:
        notes = list_notes_handler(db, session_id)
        return [
            NoteResponse(
                id=n["id"],
                session_id=session_id,
                title=n["title"],
                content=n["content"],
                tags=n.get("tags") or ""
            )
            for n in notes
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))