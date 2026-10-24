"""
PayRecover AI — Knowledge Engine & RAG REST API (Phase 5)
Provides document lifecycle management, semantic + lexical query endpoints,
case evidence introspection, and RAG health diagnostics.
"""
import json
import math
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.rbac import require_roles, require_operator
from app.models.entities import (
    User,
    UserRole,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeCategory,
    VerificationStatus
)
from app.schemas.contracts import (
    KnowledgeDocumentItem,
    KnowledgeChunkItem,
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
    KnowledgeDocumentListResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    EvidenceGroundedRecommendation,
    RAGHealthResponse
)
from app.services.ingestion_service import ingestion_service, IngestionError
from app.services.rag_service import rag_service
from app.services.embedding_service import embedding_service
from app.agents.strategist import strategist_agent, PrerequisiteContextMissingError

logger = logging.getLogger("payrecover.api.knowledge")

router = APIRouter(prefix="", tags=["Knowledge & RAG Engine"])


def _doc_to_item(doc: KnowledgeDocument, include_chunks: bool = False) -> KnowledgeDocumentItem:
    """Helper to convert KnowledgeDocument ORM model to Pydantic schema."""
    meta = None
    if doc.doc_metadata_json:
        try:
            meta = json.loads(doc.doc_metadata_json)
        except Exception:
            meta = None

    chunks_list = None
    if include_chunks and doc.chunks:
        chunks_list = []
        for chk in doc.chunks:
            chk_meta = None
            if chk.chunk_metadata_json:
                try:
                    chk_meta = json.loads(chk.chunk_metadata_json)
                except Exception:
                    chk_meta = None
            chunks_list.append(KnowledgeChunkItem(
                id=chk.id,
                document_id=chk.document_id,
                chunk_index=chk.chunk_index,
                heading=chk.heading,
                content=chk.content,
                content_hash=chk.content_hash,
                token_count=chk.token_count,
                chunk_metadata=chk_meta,
                created_at=chk.created_at
            ))

    return KnowledgeDocumentItem(
        id=doc.id,
        title=doc.title,
        category=doc.category,
        source_type=doc.source_type,
        source_reference=doc.source_reference,
        merchant_id=doc.merchant_id,
        version=doc.version,
        verification_status=doc.verification_status,
        effective_date=doc.effective_date,
        expiration_date=doc.expiration_date,
        content_hash=doc.content_hash,
        raw_content=doc.raw_content,
        doc_metadata=meta,
        chunk_count=len(doc.chunks) if doc.chunks is not None else 0,
        chunks=chunks_list,
        created_at=doc.created_at,
        updated_at=doc.updated_at
    )


# -------------------------------------------------------------
# 1. Document Management Endpoints
# -------------------------------------------------------------

@router.get("/documents", response_model=KnowledgeDocumentListResponse)
def list_knowledge_documents(
    category: Optional[str] = Query(None, description="Filter by KnowledgeCategory"),
    verification_status: Optional[str] = Query(None, description="Filter by VerificationStatus"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID (null for global)"),
    search: Optional[str] = Query(None, description="Search term in title or content"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List indexed knowledge documents with category, status, tenant filtering, and search.
    """
    query = db.query(KnowledgeDocument)

    if category:
        query = query.filter(KnowledgeDocument.category == category)
    if verification_status:
        query = query.filter(KnowledgeDocument.verification_status == verification_status)
    if merchant_id:
        query = query.filter(
            or_(
                KnowledgeDocument.merchant_id == merchant_id,
                KnowledgeDocument.merchant_id.is_(None)
            )
        )
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                KnowledgeDocument.title.ilike(search_pattern),
                KnowledgeDocument.source_reference.ilike(search_pattern),
                KnowledgeDocument.raw_content.ilike(search_pattern)
            )
        )

    total = query.count()
    total_pages = max(1, math.ceil(total / limit))
    offset = (page - 1) * limit

    documents = query.order_by(desc(KnowledgeDocument.updated_at)).offset(offset).limit(limit).all()

    # Category breakdown for quick UI metrics
    category_rows = db.query(
        KnowledgeDocument.category,
        func.count(KnowledgeDocument.id)
    ).group_by(KnowledgeDocument.category).all()
    category_counts = {cat: count for cat, count in category_rows}

    items = [_doc_to_item(doc, include_chunks=False) for doc in documents]

    return KnowledgeDocumentListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        category_counts=category_counts
    )


@router.post("/documents", response_model=KnowledgeDocumentItem, status_code=status.HTTP_201_CREATED)
def ingest_knowledge_document(
    payload: KnowledgeDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Ingest, sanitize, chunk, embed, and index a new knowledge document.
    Restricted to Operator or Admin roles.
    """
    try:
        doc = ingestion_service.ingest_document(
            db=db,
            title=payload.title,
            category=payload.category,
            source_type=payload.source_type,
            source_reference=payload.source_reference,
            raw_content=payload.raw_content,
            merchant_id=payload.merchant_id,
            verification_status=payload.verification_status or VerificationStatus.VERIFIED.value,
            effective_date=payload.effective_date,
            expiration_date=payload.expiration_date,
            doc_metadata=payload.doc_metadata
        )
        return _doc_to_item(doc, include_chunks=True)
    except IngestionError as ie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ie))
    except Exception as e:
        logger.error(f"Failed to ingest knowledge document: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to ingest knowledge document.")


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentItem)
def get_knowledge_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed knowledge document by ID including its chunk breakdown.
    """
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document '{document_id}' not found."
        )
    return _doc_to_item(doc, include_chunks=True)


@router.put("/documents/{document_id}", response_model=KnowledgeDocumentItem)
def update_knowledge_document(
    document_id: str,
    payload: KnowledgeDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Update document content or metadata and re-index chunk embeddings.
    Restricted to Operator or Admin roles.
    """
    existing_doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document '{document_id}' not found."
        )

    title = payload.title if payload.title is not None else existing_doc.title
    category = payload.category if payload.category is not None else existing_doc.category
    source_type = payload.source_type if payload.source_type is not None else existing_doc.source_type
    source_reference = payload.source_reference if payload.source_reference is not None else existing_doc.source_reference
    raw_content = payload.raw_content if payload.raw_content is not None else existing_doc.raw_content
    merchant_id = payload.merchant_id if payload.merchant_id is not None else existing_doc.merchant_id
    verification_status = payload.verification_status if payload.verification_status is not None else existing_doc.verification_status
    effective_date = payload.effective_date if payload.effective_date is not None else existing_doc.effective_date
    expiration_date = payload.expiration_date if payload.expiration_date is not None else existing_doc.expiration_date

    doc_meta = payload.doc_metadata
    if doc_meta is None and existing_doc.doc_metadata_json:
        try:
            doc_meta = json.loads(existing_doc.doc_metadata_json)
        except Exception:
            doc_meta = None

    try:
        updated_doc = ingestion_service.ingest_document(
            db=db,
            title=title,
            category=category,
            source_type=source_type,
            source_reference=source_reference,
            raw_content=raw_content,
            merchant_id=merchant_id,
            verification_status=verification_status,
            effective_date=effective_date,
            expiration_date=expiration_date,
            doc_metadata=doc_meta,
            custom_id=document_id
        )
        return _doc_to_item(updated_doc, include_chunks=True)
    except IngestionError as ie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ie))
    except Exception as e:
        logger.error(f"Failed to update document '{document_id}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update document.")


@router.delete("/documents/{document_id}")
def delete_knowledge_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Delete a document and cascade remove all its chunk embeddings.
    Restricted to Operator or Admin roles.
    """
    deleted = ingestion_service.delete_document(db=db, document_id=document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document '{document_id}' not found."
        )
    return {"success": True, "message": f"Document '{document_id}' and chunk embeddings deleted."}


# -------------------------------------------------------------
# 2. Hybrid Retrieval Query Endpoint
# -------------------------------------------------------------

@router.post("/query", response_model=KnowledgeQueryResponse)
def query_knowledge_base(
    payload: KnowledgeQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test hybrid retrieval across vector embeddings and lexical token matching.
    Includes merchant isolation, relevance thresholding, and policy conflict detection.
    """
    return rag_service.query_knowledge(
        db=db,
        query=payload.query,
        category=payload.category,
        merchant_id=payload.merchant_id or current_user.merchant_id,
        limit=payload.limit,
        relevance_threshold=payload.relevance_threshold
    )


# -------------------------------------------------------------
# 3. Case Evidence Introspection Endpoint
# -------------------------------------------------------------

@router.get("/case/{case_id}/evidence", response_model=EvidenceGroundedRecommendation)
def get_case_evidence(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inspect grounded retrieval evidence, policy citations, Wilson CI estimates,
    and guardrail constraints for a specific recovery case.
    """
    try:
        return strategist_agent.generate_evidence_grounded_strategy(
            db=db,
            recovery_case_id=case_id
        )
    except PrerequisiteContextMissingError as pe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(pe))
    except ValueError as ve:
        if "not found" in str(ve).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to generate case evidence for '{case_id}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate case evidence.")


# -------------------------------------------------------------
# 4. RAG Engine Health & Diagnostics Endpoint
# -------------------------------------------------------------

@router.get("/health", response_model=RAGHealthResponse)
def get_rag_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inspect RAG engine operational health, indexing volume, embedding model status,
    and vector search configuration.
    """
    total_docs = db.query(KnowledgeDocument).count()
    total_chunks = db.query(KnowledgeChunk).count()

    cat_rows = db.query(
        KnowledgeDocument.category,
        func.count(KnowledgeDocument.id)
    ).group_by(KnowledgeDocument.category).all()
    cat_dist = {cat: count for cat, count in cat_rows}

    latest_doc = db.query(KnowledgeDocument).order_by(desc(KnowledgeDocument.updated_at)).first()

    return RAGHealthResponse(
        status="OPERATIONAL",
        total_documents=total_docs,
        total_chunks=total_chunks,
        category_distribution=cat_dist,
        embedding_model=embedding_service.model_name,
        embedding_dimension=embedding_service.dimension,
        vector_search_mode="hybrid_dense_lexical_numpy",
        hybrid_ranking_active=True,
        last_indexed_at=latest_doc.updated_at if latest_doc else None
    )
