"""
PayRecover AI — Recovery Intelligence Evaluation CLI
Evaluates calibrated probability estimation against empirical baselines
using strict temporal train/test validation without look-ahead data leakage.
"""
import sys
import os

# Add parent directory to path so script can run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.session import SessionLocal
from app.models.entities import RecoveryOutcome
from app.services.intelligence_service import probability_estimator


def run_evaluation():
    db = SessionLocal()
    try:
        outcomes = db.query(RecoveryOutcome).order_by(RecoveryOutcome.decision_timestamp).all()
        print("==================================================================")
        print("PAYRECOVER AI — PHASE 4 RECOVERY INTELLIGENCE ENGINE EVALUATION")
        print("==================================================================")
        print(f"Total Outcomes Ingested: {len(outcomes)}")

        metrics = probability_estimator.train_and_evaluate(outcomes)

        print("\n--- SAMPLE SIZE & CLASS DISTRIBUTION ---")
        print(f"  Total Attempts Evaluated: {metrics.sample_size_total}")
        print(f"  Labeled Terminal Samples: {metrics.sample_size_labeled}")
        print(f"  Recovered Outcomes:       {metrics.recovered_count}")
        print(f"  Unsuccessful Outcomes:    {metrics.unsuccessful_count}")
        print(f"  Baseline Empirical Rate:  {metrics.baseline_recovery_rate * 100:.2f}%")

        print("\n--- TEMPORAL VALIDATION SPLIT ---")
        print(f"  Training Set (Prior 70%): {metrics.train_sample_size} cases")
        print(f"  Test Set (Holdout 30%):   {metrics.test_sample_size} cases (Out-of-Time)")
        print(f"  Data Quality Status:      {metrics.data_quality_status}")

        print("\n--- CALIBRATION & RANKING METRICS ---")
        print(f"  Baseline Brier Score:     {metrics.baseline_brier_score:.5f}")
        print(f"  Model Brier Score:        {metrics.model_brier_score:.5f} (lower is better)")
        print(f"  Brier Skill Score (BSS):  {metrics.brier_skill_score:.4f} (improvement over base rate)")
        if metrics.roc_auc is not None:
            print(f"  ROC-AUC (Mann-Whitney):   {metrics.roc_auc:.4f}")
        else:
            print(f"  ROC-AUC:                  N/A (insufficient test set class balance)")
        if metrics.expected_calibration_error is not None:
            print(f"  Expected Calib. Error:    {metrics.expected_calibration_error:.4f}")

        print("\n--- MODEL VERSION & ASSUMPTIONS ---")
        print(f"  Model Version:            {metrics.model_version}")
        print(f"  Methodology:              L2-regularized logistic calibration + Wilson score intervals")

        print("\n--- LIMITATIONS & DISCLAIMERS ---")
        for idx, lim in enumerate(metrics.limitations, 1):
            print(f"  [{idx}] {lim}")
        print("==================================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_evaluation()
