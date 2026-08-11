from app.core.llm_client import llm_client

REWRITE_SYSTEM_PROMPT = """
You are a Query Rewriter for a RAG system.
Your job is to convert ambiguous follow-up questions (like "what are its types?", "explain more", "how does it work?") into clean, standalone search queries.

RULES:
1. Look at the immediate conversation history to identify what concept "it", "its", "this", or "that" refers to.
2. If the user was asking about "Few Shot Prompting" in a recent message, rewrite "what are its types?" to:
   "What are the types of few shot prompting?"
3. Return ONLY a JSON object:
   {"intent": "RAG_SEARCH", "rewritten_query": "<standalone_query>"}
"""

def analyze_and_rewrite_query(user_message: str, chat_history: str = "") -> dict:
    prompt = f"Chat History:\n{chat_history}\n\nUser Query: {user_message}"
    try:
        result = llm_client.call_json_schema(prompt=prompt, system_prompt=SYSTEM_PROMPT)
        if "intent" in result and "rewritten_query" in result:
            return result
    except Exception:
        pass
    return {"intent": "RAG_SEARCH", "rewritten_query": user_message}