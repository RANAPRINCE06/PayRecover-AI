"""
PayRecover AI — Document Ingestion & Chunking Service (Phase 5 RAG)
Handles normalization, semantic heading-preserved chunking, content hash deduplication,
versioning, prompt injection sanitization, and embedding generation.
"""
import re
import uuid
import hashlib
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import (
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeCategory,
    VerificationStatus
)
from app.services.embedding_service import embedding_service

logger = logging.getLogger("payrecover.ingestion")

MAX_DOCUMENT_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
MIN_DOCUMENT_LENGTH_CHARS = 10
TARGET_CHUNK_SIZE_CHARS = 450
OVERLAP_CHARS = 60

# Pattern to detect prompt injection attempts in uploaded knowledge
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(guardrails|rules|limits)", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"bypass\s+human\s+approval", re.IGNORECASE),
    re.compile(r"auto-?approve\s+all", re.IGNORECASE),
]


class IngestionError(Exception):
    """Raised when document ingestion validation fails."""
    pass


class DocumentIngestionService:
    """
    Manages knowledge document ingestion lifecycle:
    Validation -> Sanitization -> Chunking -> Hashing -> Embedding -> Persistence.
    """

    @classmethod
    def calculate_hash(cls, content: str) -> str:
        """Returns hex SHA-256 hash of normalized content string."""
        normalized = cls._normalize_text(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normalizes line endings and redundant whitespace."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()

    @classmethod
    def sanitize_untrusted_content(cls, raw_text: str) -> Tuple[str, List[str]]:
        """
        Scans for prompt injection directives, neutralizing them so retrieved
        passages cannot hijack LLM execution.
        """
        sanitized = raw_text
        detected_injections = []
        for pattern in PROMPT_INJECTION_PATTERNS:
            matches = pattern.findall(sanitized)
            if matches:
                detected_injections.append(pattern.pattern)
                sanitized = pattern.sub("[FILTERED_UNTRUSTED_INSTRUCTION]", sanitized)
        return sanitized, detected_injections

    @classmethod
    def chunk_document(
        cls,
        text: str,
        document_title: str
    ) -> List[Dict[str, Any]]:
        """
        Splits Markdown or text into chunks while preserving section headings.
        Each chunk contains the active section heading and coherent body paragraphs.
        """
        lines = text.split("\n")
        chunks = []
        current_heading = document_title
        current_paragraphs = []
        current_char_count = 0

        for line in lines:
            stripped = line.strip()
            # Detect Markdown headings (# Header, ## Header, ### Header)
            if stripped.startswith("#"):
                # If we have accumulated paragraphs under prior heading, flush chunk
                if current_paragraphs:
                    body = "\n".join(current_paragraphs).strip()
                    if body:
                        chunks.append({
                            "heading": current_heading,
                            "content": f"### {current_heading}\n{body}"
                        })
                    current_paragraphs = []
                    current_char_count = 0

                # Extract new heading title
                heading_clean = stripped.lstrip("#").strip()
                if heading_clean:
                    current_heading = heading_clean
                continue

            # Accumulate body text
            if stripped:
                current_paragraphs.append(stripped)
                current_char_count += len(stripped)

                # Check if paragraph reached target size
                if current_char_count >= TARGET_CHUNK_SIZE_CHARS:
                    body = "\n".join(current_paragraphs).strip()
                    chunks.append({
                        "heading": current_heading,
                        "content": f"### {current_heading}\n{body}"
                    })
                    # Keep last paragraph for smooth boundary context
                    current_paragraphs = [current_paragraphs[-1]] if len(current_paragraphs) > 1 else []
                    current_char_count = sum(len(p) for p in current_paragraphs)

        # Flush final remaining chunk
        if current_paragraphs:
            body = "\n".join(current_paragraphs).strip()
            if body:
                chunks.append({
                    "heading": current_heading,
                    "content": f"### {current_heading}\n{body}"
                })

        # Fallback if document had no distinct headings
        if not chunks and text.strip():
            chunks.append({
                "heading": document_title,
                "content": f"### {document_title}\n{text.strip()}"
            })

        return chunks

    @classmethod
    def ingest_document(
        cls,
        db: Session,
        title: str,
        category: str,
        source_type: str,
        source_reference: str,
        raw_content: str,
        merchant_id: Optional[str] = None,
        verification_status: str = VerificationStatus.VERIFIED.value,
        effective_date: Optional[datetime] = None,
        expiration_date: Optional[datetime] = None,
        doc_metadata: Optional[Dict[str, Any]] = None,
        custom_id: Optional[str] = None
    ) -> KnowledgeDocument:
        """
        Validates, ingests, and indexes a new or updated knowledge document.
        Skips re-indexing if content hash is unchanged.
        """
        # 1. Validations
        if not title or len(title.strip()) < 3:
            raise IngestionError("Document title must be at least 3 characters.")

        if not raw_content or len(raw_content.strip()) < MIN_DOCUMENT_LENGTH_CHARS:
            raise IngestionError(f"Document content must be at least {MIN_DOCUMENT_LENGTH_CHARS} characters.")

        if len(raw_content.encode("utf-8")) > MAX_DOCUMENT_SIZE_BYTES:
            raise IngestionError(f"Document exceeds maximum size of {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)}MB.")

        # Validate category
        valid_cats = [c.value for c in KnowledgeCategory]
        if category not in valid_cats:
            raise IngestionError(f"Invalid category '{category}'. Must be one of {valid_cats}.")

        # 2. Sanitize untrusted content
        sanitized_content, injections = cls.sanitize_untrusted_content(raw_content)
        content_hash = cls.calculate_hash(sanitized_content)

        metadata_dict = doc_metadata.copy() if doc_metadata else {}
        if injections:
            metadata_dict["sanitized_injection_attempts"] = injections
            logger.warning(f"Sanitized {len(injections)} potential prompt injection pattern(s) from document '{title}'")

        # 3. Check for existing document with same ID or content hash
        doc_id = custom_id or f"doc_{uuid.uuid4().hex[:12]}"
        existing_doc = db.query(KnowledgeDocument).filter(
            (KnowledgeDocument.id == doc_id) |
            ((KnowledgeDocument.title == title) & (KnowledgeDocument.merchant_id == merchant_id))
        ).first()

        if existing_doc:
            # Check if unchanged
            if existing_doc.content_hash == content_hash and existing_doc.title == title:
                logger.info(f"Document '{title}' ({existing_doc.id}) content unchanged. Skipping chunk re-indexing.")
                return existing_doc

            # Update existing document
            logger.info(f"Document '{title}' ({existing_doc.id}) updated. Incrementing version and re-indexing chunks.")
            existing_doc.title = title
            existing_doc.category = category
            existing_doc.source_type = source_type
            existing_doc.source_reference = source_reference
            existing_doc.merchant_id = merchant_id
            existing_doc.version += 1
            existing_doc.verification_status = verification_status
            existing_doc.effective_date = effective_date
            existing_doc.expiration_date = expiration_date
            existing_doc.content_hash = content_hash
            existing_doc.raw_content = sanitized_content
            existing_doc.doc_metadata_json = json.dumps(metadata_dict)
            existing_doc.updated_at = datetime.utcnow()

            # Delete old chunks
            db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == existing_doc.id).delete()
            doc_to_chunk = existing_doc
        else:
            # Create new document
            new_doc = KnowledgeDocument(
                id=doc_id,
                title=title,
                category=category,
                source_type=source_type,
                source_reference=source_reference,
                merchant_id=merchant_id,
                version=1,
                verification_status=verification_status,
                effective_date=effective_date,
                expiration_date=expiration_date,
                content_hash=content_hash,
                raw_content=sanitized_content,
                doc_metadata_json=json.dumps(metadata_dict),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_doc)
            db.flush()
            doc_to_chunk = new_doc

        # 4. Chunk document & compute embeddings
        raw_chunks = cls.chunk_document(sanitized_content, title)
        for idx, rc in enumerate(raw_chunks):
            chunk_content = rc["content"]
            chunk_hash = hashlib.sha256(chunk_content.encode("utf-8")).hexdigest()
            # Generate 768-dim normalized embedding
            emb_vector = embedding_service.embed_text(chunk_content)
            tokens = len(chunk_content.split())

            chunk_meta = {
                "merchant_id": merchant_id,
                "category": category,
                "source_type": source_type,
                "version": doc_to_chunk.version,
                "verification_status": verification_status
            }

            chunk = KnowledgeChunk(
                id=f"chk_{uuid.uuid4().hex[:12]}",
                document_id=doc_to_chunk.id,
                chunk_index=idx,
                heading=rc["heading"],
                content=chunk_content,
                content_hash=chunk_hash,
                embedding_json=json.dumps(emb_vector),
                token_count=tokens,
                chunk_metadata_json=json.dumps(chunk_meta),
                created_at=datetime.utcnow()
            )
            db.add(chunk)

        db.commit()
        db.refresh(doc_to_chunk)
        logger.info(f"Successfully indexed document '{title}' ({doc_to_chunk.id}) with {len(raw_chunks)} chunks.")
        return doc_to_chunk

    @classmethod
    def delete_document(cls, db: Session, document_id: str) -> bool:
        """Removes a document and cascades deletion to all associated chunks/embeddings."""
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if not doc:
            return False

        db.delete(doc)
        db.commit()
        logger.info(f"Deleted document '{document_id}' and all associated chunk embeddings.")
        return True


ingestion_service = DocumentIngestionService()
