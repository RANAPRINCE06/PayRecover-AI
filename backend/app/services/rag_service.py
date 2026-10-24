"""
PayRecover AI — Hybrid Retrieval & Ranking Engine (Phase 5 RAG)
Combines dense semantic vector search (cosine similarity), lexical token overlap,
strict tenant/merchant isolation, verification weighting, and policy conflict detection.
"""
import re
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.entities import (
    KnowledgeDocument,
    KnowledgeChunk,
    VerificationStatus,
    KnowledgeCategory
)
from app.schemas.contracts import (
    RetrievedPassage,
    KnowledgeQueryResponse
)
from app.services.embedding_service import embedding_service

logger = logging.getLogger("payrecover.rag")


class RAGRetrievalService:
    """
    Enterprise RAG retrieval service providing hybrid semantic + lexical search,
    strict multi-tenant isolation, metadata filtering, and policy conflict detection.
    """

    @classmethod
    def _calculate_lexical_overlap(cls, query: str, content: str) -> float:
        """
        Calculates term frequency / token overlap between query and chunk content.
        Uses stopword filtering and token matching.
        """
        stopwords = {
            "the", "a", "an", "in", "on", "of", "to", "for", "is", "are", "and",
            "or", "with", "as", "by", "at", "from", "that", "this", "it"
        }
        q_tokens = [
            t for t in re.findall(r"\w+", query.lower())
            if len(t) > 2 and t not in stopwords
        ]
        if not q_tokens:
            return 0.0

        content_lower = content.lower()
        matched = 0
        for token in q_tokens:
            if token in content_lower:
                matched += 1

        # Token jaccard-like score with term frequency bonus
        base_score = matched / len(q_tokens)
        # Extra bonus for exact phrase match
        if query.lower() in content_lower:
            base_score = min(1.0, base_score + 0.25)
        return float(base_score)

    @classmethod
    def detect_policy_conflicts(cls, passages: List[RetrievedPassage]) -> List[str]:
        """
        Scans retrieved passages for contradictory directives (e.g., channel allowlist conflicts,
        different retry limits, discount cap mismatches).
        """
        conflicts = []
        policy_passages = [p for p in passages if p.category == KnowledgeCategory.MERCHANT_POLICY.value]
        
        # 1. Channel allowlist checks
        whatsapp_allowed = None
        voice_allowed = None
        for p in policy_passages:
            content_lower = p.content.lower()
            if "whatsapp" in content_lower:
                if "never use whatsapp" in content_lower or "whatsapp not permitted" in content_lower or "whatsapp prohibited" in content_lower:
                    if whatsapp_allowed is True:
                        conflicts.append(f"Channel Conflict: WhatsApp permitted in '{whatsapp_doc}' but prohibited in '{p.document_title}'")
                    whatsapp_allowed = False
                    whatsapp_doc = p.document_title
                elif "whatsapp permitted" in content_lower or "whatsapp allowed" in content_lower or "primary channel: whatsapp" in content_lower:
                    if whatsapp_allowed is False:
                        conflicts.append(f"Channel Conflict: WhatsApp prohibited in '{whatsapp_doc}' but allowed in '{p.document_title}'")
                    whatsapp_allowed = True
                    whatsapp_doc = p.document_title

        # 2. Max discount discrepancies
        discounts_found = []
        for p in policy_passages:
            matches = re.findall(r"max(?:imum)?\s+discount(?:\s+cap)?(?:\s+is)?(?:\s*:)?\s*(\d+)%", p.content, re.IGNORECASE)
            for m in matches:
                discounts_found.append((int(m), p.document_title))

        if len(discounts_found) > 1:
            disc_values = set(d[0] for d in discounts_found)
            if len(disc_values) > 1:
                conflicts.append(f"Discount Policy Discrepancy: Conflicting caps found {discounts_found}. Strictest cap will be enforced.")

        return conflicts

    @classmethod
    def query_knowledge(
        cls,
        db: Session,
        query: str,
        category: Optional[str] = None,
        merchant_id: Optional[str] = None,
        limit: int = 5,
        relevance_threshold: float = 0.35
    ) -> KnowledgeQueryResponse:
        """
        Executes hybrid semantic vector + lexical search across indexed knowledge chunks.
        Strictly enforces tenant isolation: returns chunks where merchant_id == requested OR merchant_id IS NULL.
        """
        start_time = time.time()
        now = datetime.utcnow()

        # 1. Build database filter
        chunk_query = db.query(KnowledgeChunk).join(
            KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id
        ).filter(
            KnowledgeDocument.verification_status != VerificationStatus.DEPRECATED.value,
            or_(
                KnowledgeDocument.effective_date.is_(None),
                KnowledgeDocument.effective_date <= now
            ),
            or_(
                KnowledgeDocument.expiration_date.is_(None),
                KnowledgeDocument.expiration_date >= now
            )
        )

        # Enforce merchant isolation
        if merchant_id:
            chunk_query = chunk_query.filter(
                or_(
                    KnowledgeDocument.merchant_id == merchant_id,
                    KnowledgeDocument.merchant_id.is_(None)
                )
            )
        else:
            # Platform global only if merchant_id not provided
            chunk_query = chunk_query.filter(KnowledgeDocument.merchant_id.is_(None))

        if category:
            chunk_query = chunk_query.filter(KnowledgeDocument.category == category)

        candidate_chunks = chunk_query.all()
        if not candidate_chunks:
            return KnowledgeQueryResponse(
                query=query,
                total_retrieved=0,
                is_sufficient=False,
                highest_score=0.0,
                passages=[],
                policy_conflicts_detected=[],
                latency_ms=int((time.time() - start_time) * 1000)
            )

        # 2. Compute query embedding vector
        q_vector = embedding_service.embed_text(query)

        # 3. Score candidates with hybrid ranking
        scored_passages: List[RetrievedPassage] = []
        for chk in candidate_chunks:
            doc = chk.document
            # Deserialize embedding vector
            try:
                emb_vec = json.loads(chk.embedding_json)
                semantic_score = embedding_service.cosine_similarity(q_vector, emb_vec)
            except Exception:
                semantic_score = 0.0

            # Lexical score
            lexical_score = cls._calculate_lexical_overlap(query, chk.content)

            # Metadata boosts
            is_merchant_spec = (doc.merchant_id is not None and doc.merchant_id == merchant_id)
            merchant_boost = 0.15 if is_merchant_spec else 0.0
            verified_boost = 0.10 if doc.verification_status == VerificationStatus.VERIFIED.value else 0.0
            conflicted_penalty = -0.25 if doc.verification_status == VerificationStatus.CONFLICTED.value else 0.0

            # Hybrid score formula
            combined_score = float(np.clip(
                (0.55 * semantic_score) + (0.35 * lexical_score) + merchant_boost + verified_boost + conflicted_penalty,
                0.0,
                1.0
            ))

            if combined_score >= relevance_threshold:
                method = "hybrid" if (semantic_score > 0.1 and lexical_score > 0.1) else (
                    "semantic" if semantic_score >= lexical_score else "lexical"
                )

                passage = RetrievedPassage(
                    chunk_id=chk.id,
                    document_id=doc.id,
                    document_title=doc.title,
                    category=doc.category,
                    source_type=doc.source_type,
                    source_reference=doc.source_reference,
                    merchant_id=doc.merchant_id,
                    heading=chk.heading,
                    content=chk.content,
                    similarity_score=round(semantic_score, 4),
                    lexical_score=round(lexical_score, 4),
                    combined_score=round(combined_score, 4),
                    verification_status=doc.verification_status,
                    version=doc.version,
                    is_merchant_specific=is_merchant_spec,
                    retrieval_method=method,
                    detected_conflicts=[]
                )
                scored_passages.append(passage)

        # 4. Sort by combined score descending
        scored_passages.sort(key=lambda p: p.combined_score, reverse=True)

        # 5. Deduplicate overlapping chunks from same document section
        seen_headings = set()
        deduped_passages = []
        for p in scored_passages:
            key = (p.document_id, p.heading)
            if key not in seen_headings:
                seen_headings.add(key)
                deduped_passages.append(p)
            if len(deduped_passages) >= limit:
                break

        # 6. Detect policy conflicts across selected passages
        conflicts = cls.detect_policy_conflicts(deduped_passages)
        for p in deduped_passages:
            if conflicts and p.category == KnowledgeCategory.MERCHANT_POLICY.value:
                p.detected_conflicts = conflicts

        highest = deduped_passages[0].combined_score if deduped_passages else 0.0
        is_sufficient = (len(deduped_passages) > 0 and highest >= 0.45)

        latency_ms = int((time.time() - start_time) * 1000)
        return KnowledgeQueryResponse(
            query=query,
            total_retrieved=len(deduped_passages),
            is_sufficient=is_sufficient,
            highest_score=round(highest, 4),
            passages=deduped_passages,
            policy_conflicts_detected=conflicts,
            latency_ms=latency_ms
        )


rag_service = RAGRetrievalService()
