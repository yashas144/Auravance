from __future__ import annotations

import math
import re
from collections import Counter

from app.core.db import fetch_knowledge_chunks, fetch_knowledge_corpus_stats, fetch_knowledge_documents
from app.models.schemas import KnowledgeDocumentResponse, KnowledgeSearchResultResponse
from app.services.openai_client import OpenAIRagError, embed_texts, has_openai_api_key


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return dot / (left_norm * right_norm)


class KnowledgeService:
    def list_documents(self) -> list[KnowledgeDocumentResponse]:
        return [KnowledgeDocumentResponse(**row) for row in fetch_knowledge_documents()]

    def _query_vector(self, query_tokens: list[str], stats: dict[str, dict]) -> dict[str, float]:
        if not query_tokens:
            return {}
        counts = Counter(query_tokens)
        total = sum(counts.values()) or 1
        vector = {
            token: (count / total) * stats[token]["idf"]
            for token, count in counts.items()
            if token in stats
        }
        magnitude = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
        return {token: weight / magnitude for token, weight in vector.items()}

    def retrieve(self, query: str, limit: int = 3) -> list[dict]:
        query_tokens = _tokenize(query)
        chunks = fetch_knowledge_chunks()
        if not query_tokens:
            return [{**chunk, "score": 0.0} for chunk in chunks[:limit]]

        stats = fetch_knowledge_corpus_stats()
        query_vector = self._query_vector(query_tokens, stats)
        query_counts = Counter(query_tokens)
        query_embedding: list[float] = []
        if has_openai_api_key():
            try:
                embeddings = embed_texts([query])
                query_embedding = embeddings[0] if embeddings else []
            except OpenAIRagError:
                query_embedding = []
        scored: list[tuple[float, dict]] = []
        for chunk in chunks:
            keyword_overlap = sum(query_counts[token] for token in query_counts if token in chunk["content"].lower())
            vector_score = sum(
                query_vector[token] * float(chunk["vector"].get(token, 0.0))
                for token in query_vector
            )
            embedding_score = _cosine_similarity(query_embedding, chunk.get("embedding", []))
            normalized_keyword_overlap = keyword_overlap / max(len(query_tokens), 1)
            score = (
                (embedding_score * 0.70)
                + (vector_score * 0.20)
                + (normalized_keyword_overlap * 0.10)
            )
            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            **chunk,
                            "score": round(float(score), 6),
                            "embedding_score": round(float(embedding_score), 6),
                            "keyword_score": round(float(normalized_keyword_overlap), 6),
                            "tfidf_score": round(float(vector_score), 6),
                        },
                    )
                )

        scored.sort(key=lambda item: (item[0], -item[1]["chunk_index"]), reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def search(self, query: str, limit: int = 5) -> list[KnowledgeSearchResultResponse]:
        matches = self.retrieve(query, limit=limit)
        results: list[KnowledgeSearchResultResponse] = []
        for match in matches:
            preview = match["content"][:220].strip()
            results.append(
                KnowledgeSearchResultResponse(
                    document_id=match["document_id"],
                    title=match["title"],
                    vendor=match["vendor"],
                    source_path=match["source_path"],
                    source_type=match["source_type"],
                    chunk_index=match["chunk_index"],
                    score=float(match.get("score", 0.0)),
                    content_preview=f"{preview}..." if len(match["content"]) > 220 else preview,
                )
            )
        return results


knowledge_service = KnowledgeService()
