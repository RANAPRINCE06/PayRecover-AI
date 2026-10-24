"""
PayRecover AI — RAG Retrieval & Source Attribution Evaluation Framework (Phase 5)
Evaluates Recall@K, Precision@K, Mean Reciprocal Rank (MRR), source attribution accuracy,
relevance gating, and policy conflict detection against benchmark dataset.
"""
import os
import json
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine, Base
from app.db.seed_data import seed_database
from app.services.rag_service import rag_service
from app.models.entities import KnowledgeDocument

logger = logging.getLogger("payrecover.rag.evaluation")

DATASET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "rag",
    "evaluation_dataset.json"
)


def run_evaluation(dataset_path: str = DATASET_PATH, k: int = 5) -> Dict[str, Any]:
    """
    Executes benchmark queries against indexed knowledge base and calculates metrics.
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Evaluation benchmark dataset not found at: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        benchmark = json.load(f)

    test_cases: List[Dict[str, Any]] = benchmark.get("test_cases", [])
    if not test_cases:
        raise ValueError("No test cases found in evaluation dataset.")

    # Ensure database is initialized & seeded
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if seed documents exist, if not, seed
        doc_count = db.query(KnowledgeDocument).count()
        if doc_count < 3:
            logger.info("Knowledge base not populated. Seeding initial documents...")
            seed_database(db=db)

        recall_scores: List[float] = []
        precision_scores: List[float] = []
        reciprocal_ranks: List[float] = []
        attribution_scores: List[float] = []
        conflict_matches: List[float] = []
        gating_matches: List[float] = []
        case_results: List[Dict[str, Any]] = []

        for tc in test_cases:
            tc_id = tc["id"]
            query = tc["query"]
            expected_docs = tc.get("expected_document_ids", [])
            expected_heading = tc.get("expected_heading_substring")
            expect_insufficient = tc.get("expect_insufficient", False)
            expected_conflict = tc.get("expected_conflict", False)
            merchant_id = tc.get("merchant_id", "merchant_primary")

            res = rag_service.query_knowledge(
                db=db,
                query=query,
                merchant_id=merchant_id,
                limit=k,
                relevance_threshold=0.35
            )

            passages = res.passages

            # Gating check
            if expect_insufficient:
                is_gating_correct = (not res.is_sufficient) or (len(passages) == 0)
                gating_matches.append(1.0 if is_gating_correct else 0.0)
                recall_scores.append(1.0 if is_gating_correct else 0.0)
                reciprocal_ranks.append(1.0 if is_gating_correct else 0.0)
                precision_scores.append(1.0 if is_gating_correct else 0.0)
                attribution_scores.append(1.0)
                conflict_matches.append(1.0)
                case_results.append({
                    "id": tc_id,
                    "query": query,
                    "retrieved_count": len(passages),
                    "is_sufficient": res.is_sufficient,
                    "expected_insufficient": True,
                    "passed": is_gating_correct
                })
                continue

            # Standard Retrieval Checks
            retrieved_doc_ids = [p.document_id for p in passages]

            # 1. Recall@K
            found_expected = any(doc_id in retrieved_doc_ids for doc_id in expected_docs)
            if not found_expected and expected_heading:
                found_expected = any(expected_heading.lower() in p.heading.lower() for p in passages)
            recall = 1.0 if found_expected else 0.0
            recall_scores.append(recall)

            # 2. Precision@K
            relevant_count = sum(1 for p in passages if p.document_id in expected_docs or (expected_heading and expected_heading.lower() in p.heading.lower()))
            precision = round(relevant_count / max(1, len(passages)), 4) if passages else 0.0
            precision_scores.append(precision)

            # 3. Reciprocal Rank (RR)
            rr = 0.0
            for rank_idx, p in enumerate(passages, start=1):
                if p.document_id in expected_docs or (expected_heading and expected_heading.lower() in p.heading.lower()):
                    rr = 1.0 / rank_idx
                    break
            reciprocal_ranks.append(rr)

            # 4. Source Attribution Accuracy
            # Each retrieved passage must contain valid document_id, heading, and non-empty content
            valid_attributions = sum(
                1 for p in passages
                if p.document_id and p.document_title and p.heading and len(p.content) > 10 and p.chunk_id
            )
            attribution_acc = (valid_attributions / len(passages)) if passages else 1.0
            attribution_scores.append(attribution_acc)

            # 5. Policy Conflict Detection
            detected_conflict = len(res.policy_conflicts_detected) > 0
            conflict_correct = (detected_conflict == expected_conflict)
            conflict_matches.append(1.0 if conflict_correct else 0.0)

            passed = (recall == 1.0 and rr > 0.0)
            case_results.append({
                "id": tc_id,
                "query": query,
                "recall_at_k": recall,
                "precision_at_k": precision,
                "reciprocal_rank": round(rr, 4),
                "top_retrieved": [f"[{p.document_title}] {p.heading} (score: {p.combined_score})" for p in passages[:2]],
                "passed": passed
            })

        mean_recall = round(sum(recall_scores) / len(recall_scores), 4)
        mean_precision = round(sum(precision_scores) / len(precision_scores), 4)
        mrr = round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4)
        mean_attribution = round(sum(attribution_scores) / len(attribution_scores), 4)
        mean_conflict = round(sum(conflict_matches) / len(conflict_matches), 4)
        overall_accuracy = round(sum(1 for c in case_results if c.get("passed", False)) / len(case_results), 4)

        report = {
            "benchmark_suite": benchmark.get("benchmark_suite", "PayRecover AI RAG"),
            "total_test_cases": len(test_cases),
            "k": k,
            "metrics": {
                "mean_recall_at_k": mean_recall,
                "mean_precision_at_k": mean_precision,
                "mean_reciprocal_rank_mrr": mrr,
                "source_attribution_accuracy": mean_attribution,
                "conflict_detection_accuracy": mean_conflict,
                "overall_benchmark_pass_rate": overall_accuracy
            },
            "cases": case_results
        }

        return report

    finally:
        db.close()


def print_evaluation_report(report: Dict[str, Any]):
    """Pretty prints the evaluation benchmark metrics in a clean CLI table."""
    print("=" * 72)
    print(f"  {report['benchmark_suite']} — Benchmark Report")
    print("=" * 72)
    metrics = report["metrics"]
    print(f"Total Test Cases Evaluated : {report['total_test_cases']}")
    print(f"Retrieval Depth (K)        : {report['k']}")
    print(f"Mean Recall@{report['k']}            : {metrics['mean_recall_at_k'] * 100:.1f}%")
    print(f"Mean Precision@{report['k']}         : {metrics['mean_precision_at_k'] * 100:.1f}%")
    print(f"Mean Reciprocal Rank (MRR) : {metrics['mean_reciprocal_rank_mrr']:.4f}")
    print(f"Source Attribution Accuracy: {metrics['source_attribution_accuracy'] * 100:.1f}%")
    print(f"Conflict Detection Acc.    : {metrics['conflict_detection_accuracy'] * 100:.1f}%")
    print(f"Overall Benchmark Pass Rate: {metrics['overall_benchmark_pass_rate'] * 100:.1f}%")
    print("=" * 72)
    print("Case Breakdown:")
    for c in report["cases"]:
        status = "PASS" if c.get("passed", False) else "FAIL"
        print(f" [{status}] {c['id']}: {c['query'][:45]}... (RR: {c.get('reciprocal_rank', 'N/A')})")
    print("=" * 72)


if __name__ == "__main__":
    report = run_evaluation()
    print_evaluation_report(report)
