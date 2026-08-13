import logging
import re
from collections import Counter

import chromadb
from chromadb.utils import embedding_functions
from app.core.config import settings

logger = logging.getLogger("askly.retriever")


class VectorRetriever:
    """Hybrid Chroma retriever with semantic + exact lexical search."""

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "askly_knowledge"

    STOPWORDS = {
        "what", "is", "are", "was", "were", "the", "a", "an",
        "of", "to", "for", "in", "on", "and", "or", "with", "from",
        "does", "do", "did", "how", "why", "when", "where", "who",
        "which", "can", "could", "would", "should", "this", "that",
        "these", "those", "it", "its", "they", "them", "their",
        "pdf", "document", "mention", "mentioned", "tell", "explain",
        "please", "based",
    }

    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_DIR
        )
        self.embedding_fn = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.EMBEDDING_MODEL
            )
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
        )
        logger.info(
            "Retriever initialized | collection=%s | count=%s | model=%s",
            self.collection.name,
            self.collection.count(),
            self.EMBEDDING_MODEL,
        )

    # --------------------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        text = str(text or "")
        text = text.replace("\\_", "_")
        text = text.replace("–", "-").replace("—", "-").replace("‑", "-")
        text = text.lower()
        text = re.sub(r"[^\w.\-]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        normalized = cls._normalize(text)
        return normalized.split() if normalized else []

    @staticmethod
    def _stem_token(token: str) -> str:
        """Safe lightweight normalization; NOT a classmethod."""
        token = token.lower().strip()
        if not token:
            return ""

        # Preserve technical identifiers.
        if (
            "-" in token
            or "_" in token
            or "." in token
            or any(ch.isdigit() for ch in token)
        ):
            return token

        if len(token) > 4 and token.endswith("ies"):
            return token[:-3] + "y"

        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            return token[:-1]

        return token

    @classmethod
    def _important_tokens(cls, text: str) -> list[str]:
        result = []
        for token in cls._tokens(text):
            if token in cls.STOPWORDS or len(token) <= 1:
                continue
            normalized = cls._stem_token(token)
            if normalized:
                result.append(normalized)
        return result

    # --------------------------------------------------------------
    # LEXICAL SCORE
    # --------------------------------------------------------------

    @classmethod
    def _lexical_score(cls, query: str, document: str) -> float:
        query_normalized = cls._normalize(query)
        document_normalized = cls._normalize(document)

        if not query_normalized or not document_normalized:
            return 0.0

        query_tokens = cls._important_tokens(query)
        document_tokens = cls._tokens(document)

        if not query_tokens or not document_tokens:
            return 0.0

        normalized_document_tokens = [
            cls._stem_token(token) for token in document_tokens
        ]
        document_counter = Counter(normalized_document_tokens)
        unique_query_tokens = set(query_tokens)

        matched = sum(
            1 for token in unique_query_tokens
            if token in document_counter
        )
        overlap_score = matched / max(len(unique_query_tokens), 1)

        important_phrase = " ".join(query_tokens)
        phrase_score = (
            1.0
            if len(query_tokens) >= 2
            and important_phrase in document_normalized
            else 0.0
        )

        technical_score = 0.0
        for original_token in re.findall(
            r"[A-Za-z0-9_.-]+", str(query)
        ):
            normalized_token = original_token.lower()
            is_technical = (
                "-" in original_token
                or "_" in original_token
                or "." in original_token
                or any(ch.isdigit() for ch in original_token)
                or (
                    any(ch.isupper() for ch in original_token)
                    and len(original_token) >= 3
                )
            )
            if is_technical and normalized_token in document_counter:
                technical_score += 0.30

        technical_score = min(technical_score, 0.60)

        repeated_score = min(
            sum(
                0.05 for token in unique_query_tokens
                if document_counter.get(token, 0) >= 2
            ),
            0.20,
        )

        return min(
            overlap_score * 0.60
            + phrase_score * 0.25
            + technical_score
            + repeated_score,
            1.0,
        )

    # --------------------------------------------------------------
    # SEMANTIC + HYBRID SCORE
    # --------------------------------------------------------------

    @staticmethod
    def _semantic_score(distance) -> float:
        try:
            distance = max(float(distance), 0.0)
        except (TypeError, ValueError):
            return 0.0
        return 1.0 / (1.0 + distance)

    @staticmethod
    def _combined_score(semantic_score: float, lexical_score: float) -> float:
        # Exact technical/lexical evidence gets priority.
        if lexical_score >= 0.95:
            return semantic_score * 0.25 + lexical_score * 0.75
        if lexical_score >= 0.50:
            return semantic_score * 0.40 + lexical_score * 0.60
        return semantic_score * 0.70 + lexical_score * 0.30

    # --------------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------------

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        query = str(query or "").strip()
        if not query:
            return []

        try:
            top_k = max(1, int(top_k))
        except (TypeError, ValueError):
            top_k = 4

        collection_count = self.collection.count()
        if collection_count <= 0:
            logger.warning("Retriever collection is empty.")
            return []

        candidate_k = min(max(top_k * 4, 12), collection_count)
        candidates = {}

        # 1) Semantic candidates from Chroma.
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=candidate_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Chroma semantic search failed.")
            return []

        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        for i, document in enumerate(docs):
            if not document:
                continue

            metadata = (
                metas[i]
                if i < len(metas) and metas[i]
                else {}
            )
            distance = distances[i] if i < len(distances) else None
            key = self._candidate_key(document, metadata)

            candidates[key] = {
                "content": document,
                "source": metadata.get("source", "unknown"),
                "metadata": metadata,
                "semantic_score": self._semantic_score(distance),
                "lexical_score": 0.0,
            }

        # 2) Exact lexical search over ALL stored chunks.
        # This is intentional for a small local PDF collection.
        try:
            all_results = self.collection.get(
                include=["documents", "metadatas"]
            )
        except Exception:
            logger.exception("Failed to load chunks for lexical search.")
            all_results = {"documents": [], "metadatas": []}

        all_docs = all_results.get("documents") or []
        all_metas = all_results.get("metadatas") or []
        lexical_matches = 0

        for i, document in enumerate(all_docs):
            if not document:
                continue

            metadata = (
                all_metas[i]
                if i < len(all_metas) and all_metas[i]
                else {}
            )
            lexical = self._lexical_score(query, document)
            if lexical <= 0:
                continue

            lexical_matches += 1
            key = self._candidate_key(document, metadata)

            if key in candidates:
                candidates[key]["lexical_score"] = lexical
            else:
                candidates[key] = {
                    "content": document,
                    "source": metadata.get("source", "unknown"),
                    "metadata": metadata,
                    "semantic_score": 0.0,
                    "lexical_score": lexical,
                }

        # 3) Hybrid reranking.
        ranked = []
        for item in candidates.values():
            semantic = float(item.get("semantic_score", 0.0))
            lexical = float(item.get("lexical_score", 0.0))
            item["combined_score"] = self._combined_score(
                semantic, lexical
            )
            ranked.append(item)

        ranked.sort(
            key=lambda x: (
                x["combined_score"],
                x["lexical_score"],
                x["semantic_score"],
            ),
            reverse=True,
        )

        # 4) Return unique chunks.
        final_results = []
        seen = set()

        for item in ranked:
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            normalized = self._normalize(content)
            if normalized in seen:
                continue

            seen.add(normalized)
            final_results.append({
                "content": content,
                "source": item.get("source", "unknown"),
            })

            if len(final_results) >= top_k:
                break

        logger.info(
            "HYBRID RETRIEVAL | query=%r | collection=%d | "
            "semantic_candidates=%d | lexical_matches=%d | final=%d",
            query,
            collection_count,
            len(docs),
            lexical_matches,
            len(final_results),
        )

        for rank, item in enumerate(ranked[:top_k], start=1):
            preview = str(item.get("content", "")).replace("\n", " ").strip()
            if len(preview) > 180:
                preview = preview[:180] + "..."

            logger.info(
                "RANK %d | semantic=%.4f | lexical=%.4f | "
                "combined=%.4f | source=%s | %s",
                rank,
                float(item.get("semantic_score", 0.0)),
                float(item.get("lexical_score", 0.0)),
                float(item.get("combined_score", 0.0)),
                item.get("source", "unknown"),
                preview,
            )

        return final_results

    @staticmethod
    def _candidate_key(content: str, metadata: dict) -> str:
        metadata = metadata or {}
        chunk_id = (
            metadata.get("chunk_id")
            or metadata.get("id")
            or metadata.get("chunk")
        )

        if chunk_id:
            return f"id::{chunk_id}"

        return "content::" + str(content)


retriever = VectorRetriever()