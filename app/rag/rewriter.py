import logging
import re
from typing import Optional

from app.core.llm_client import llm_client

logger = logging.getLogger("askly.rewriter")

REWRITE_SYSTEM_PROMPT = """
You are Askly's universal query rewriter for an AI assistant handling both PDF-grounded RAG retrieval and general/out-of-PDF conversational queries.

Your ONLY job is to rewrite the CURRENT USER QUESTION into ONE standalone query suitable for search, context matching, or general answering.

Return ONLY valid JSON:
{
  "intent": "RAG_SEARCH",
  "rewritten_query": "..."
}

Rules:
1. Rewrite only the current question.
2. If it is already standalone, preserve it and do not inject old context.
3. Resolve references such as it, its, they, them, this, that, these, those, etc., using the most recent relevant conversation history.
4. This applies universally to BOTH PDF-based questions AND general out-of-PDF knowledge questions.
5. Do not answer the question.
6. Do not invent facts or use outside knowledge.
7. Preserve technical names exactly.
8. A genuinely new topic must remain a new topic.
"""

REFERENCE_WORDS = {
    "it", "its", "they", "them", "this", "that", "these", "those"
}

def clean(text: str) -> str:
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in text.split("\n")]
    return "\n".join(x for x in lines if x)

def flatten(text: str) -> str:
    return re.sub(r"\s+", " ", clean(text)).strip()

def extract_turns(history: str) -> list[tuple[str, str]]:
    history = clean(history)
    if not history:
        return []

    pattern = re.compile(
        r"(?im)^\s*(user|human|assistant|ai)\s*:\s*(.*?)(?=^\s*(?:user|human|assistant|ai)\s*:|\Z)",
        re.DOTALL,
    )

    turns = []
    for match in pattern.finditer(history):
        role = match.group(1).lower()
        content = flatten(match.group(2))
        if content:
            turns.append((role, content))
    return turns

def previous_user_messages(history: str) -> list[str]:
    return [
        text for role, text in extract_turns(history)
        if role in {"user", "human"}
    ]

def extract_topic(question: str) -> Optional[str]:
    q = flatten(question).rstrip(" ?.!")

    patterns = [
        r"^(?:what|which)\s+(?:is|are)\s+(.+)$",
        r"^(?:explain|describe)\s+(.+)$",
        r"^tell\s+me\s+about\s+(.+)$",
        r"^can\s+you\s+explain\s+(.+)$",
        r"^(?:define|meaning\s+of)\s+(.+)$",
        r"^what\s+does\s+(.+?)\s+mean$",
        r"^how\s+does\s+(.+?)\s+work$",
    ]

    for pattern in patterns:
        m = re.match(pattern, q, re.IGNORECASE)
        if m:
            topic = m.group(1).strip()
            topic = re.sub(
                r"\s+(?:in|according to)\s+the\s+(?:pdf|document)$",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip(" '\"")
            if topic:
                return topic
    return None

def previous_topics(history: str) -> list[str]:
    result = []
    for question in reversed(previous_user_messages(history)):
        topic = extract_topic(question)
        if topic:
            result.append(topic)
    return result

def looks_like_followup(query: str) -> bool:
    q = flatten(query).lower()

    tokens = set(re.findall(r"\b[\w'-]+\b", q))
    if tokens & REFERENCE_WORDS:
        return True

    reference_phrases = (
        "the first one", "the second one", "the other one",
        "the former", "the latter", "these vectors",
        "those vectors", "that model", "this model",
        "that method", "this method",
    )
    if any(x in q for x in reference_phrases):
        return True

    patterns = [
        r"^\s*why\s+(?:is|are)\s+(?:it|this|that|they|these|those)\b",
        r"^\s*how\s+does\s+(?:it|this|that)\s+work\b",
        r"^\s*what\s+are\s+(?:its|their)\b",
        r"^\s*explain\s+(?:it|this|that)\b",
        r"^\s*can\s+you\s+explain\s+(?:it|this|that)\b",
        r"^\s*tell\s+me\s+more\b",
        r"^\s*what\s+about\s+(?:it|this|that)\b",
        r"^\s*(?:what|which)\s+model\b.*\b(?:it|them|this|that|these|those|vectors)\b",
        r"^\s*how\s+many\b.*\b(?:it|this|that|these|those)\b",
        r"^\s*(?:and\s+)?the\s+(?:first|second|other)\s+one\b",
    ]
    return any(re.search(p, q, re.IGNORECASE) for p in patterns)

def deterministic_rewrite(
    user_message: str,
    chat_history: str,
) -> Optional[str]:
    query = flatten(user_message)
    if not query:
        return ""

    if not chat_history.strip() or not looks_like_followup(query):
        return None

    topics = previous_topics(chat_history)
    if not topics:
        return None

    topic = topics[0]
    q = query.lower()

    if re.search(
        r"\b(?:which|what)\s+model\b.*\b(?:it|them|this|that|these|those|vectors)\b",
        q,
        re.IGNORECASE,
    ):
        return re.sub(
            r"\b(?:it|them|this|that|these|those|vectors)\b",
            topic,
            query,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    if re.fullmatch(
        r"how\s+many\s+dimensions\s+does\s+(?:it|this|that)\s+produce\??",
        q,
        re.IGNORECASE,
    ):
        return f"How many dimensions does the {topic} model produce?"

    m = re.fullmatch(
        r"why\s+is\s+(?:it|this|that)\s+(useful|important)\??",
        q,
        re.IGNORECASE,
    )
    if m:
        return f"Why is {topic} {m.group(1)}?"

    m = re.fullmatch(
        r"why\s+are\s+(?:they|these|those)\s+(useful|important)\??",
        q,
        re.IGNORECASE,
    )
    if m:
        return f"Why are {topic} {m.group(1)}?"

    if re.fullmatch(
        r"how\s+does\s+(?:it|this|that)\s+work\??",
        q,
        re.IGNORECASE,
    ):
        return f"How does {topic} work?"

    m = re.fullmatch(
        r"what\s+are\s+(?:its|their)\s+(uses|types|features)\??",
        q,
        re.IGNORECASE,
    )
    if m:
        return f"What are the {m.group(1)} of {topic}?"

    if re.fullmatch(
        r"(?:explain|describe)\s+(?:it|this|that)\.?",
        q,
        re.IGNORECASE,
    ):
        return f"Explain {topic}."

    if re.fullmatch(
        r"can\s+you\s+explain\s+(?:it|this|that)\??",
        q,
        re.IGNORECASE,
    ):
        return f"Explain {topic}."

    if re.fullmatch(
        r"tell\s+me\s+more(?:\s+about\s+(?:it|this|that))?\??",
        q,
        re.IGNORECASE,
    ):
        return f"Explain {topic} in more detail."

    if re.fullmatch(
        r"what\s+about\s+(?:it|this|that)\??",
        q,
        re.IGNORECASE,
    ):
        return f"What about {topic}?"

    for pattern in (
        r"\bthem\b", r"\bthey\b", r"\btheir\b",
        r"\bthese\b", r"\bthose\b",
        r"\bit\b", r"\bits\b", r"\bthis\b", r"\bthat\b",
    ):
        rewritten = re.sub(
            pattern, topic, query, count=1, flags=re.IGNORECASE
        )
        if rewritten != query:
            return rewritten.strip()

    return None

def validate_result(result) -> Optional[dict]:
    if not isinstance(result, dict):
        return None

    rewritten = flatten(result.get("rewritten_query", ""))
    if not rewritten:
        return None

    return {
        "intent": "RAG_SEARCH",
        "rewritten_query": rewritten,
    }

def analyze_and_rewrite_query(
    user_message: str,
    chat_history: str = "",
) -> dict:
    user_message = flatten(user_message)
    chat_history = clean(chat_history)

    if not user_message:
        return {
            "intent": "RAG_SEARCH",
            "rewritten_query": "",
        }

    deterministic = deterministic_rewrite(user_message, chat_history)
    if deterministic is not None:
        logger.info(
            "QUERY REWRITE | method=deterministic | original=%r | rewritten=%r",
            user_message,
            deterministic,
        )
        return {
            "intent": "RAG_SEARCH",
            "rewritten_query": deterministic,
        }

    prompt = f"""
PREVIOUS CONVERSATION:
======================
{chat_history or "(none)"}
======================

CURRENT USER QUESTION:
======================
{user_message}
======================

Rewrite the current user question into ONE standalone search query. 
This applies universally whether the topic is inside an uploaded PDF or part of general out-of-PDF conversation.

Resolve references using the most recent relevant context.
Do NOT force an old topic into a genuinely new question.
Do not answer the question.
Do not invent facts.
Preserve technical identifiers exactly.

Return ONLY valid JSON:
{{
  "intent": "RAG_SEARCH",
  "rewritten_query": "standalone query"
}}
"""

    try:
        result = llm_client.call_json_schema(
            prompt=prompt.strip(),
            system_prompt=REWRITE_SYSTEM_PROMPT,
        )
        validated = validate_result(result)

        if validated:
            logger.info(
                "QUERY REWRITE | method=LLM-Universal | original=%r | rewritten=%r",
                user_message,
                validated["rewritten_query"],
            )
            return validated

    except Exception:
        logger.exception("Query rewriting LLM failed; using original query.")

    logger.warning("QUERY REWRITE FALLBACK | query=%r", user_message)
    return {
        "intent": "RAG_SEARCH",
        "rewritten_query": user_message,
    }

rewrite_query = analyze_and_rewrite_query


