"""
RAG Evaluation Runner

Usage:
    python evaluation/run_eval.py              # Full evaluation (50 questions)
    python evaluation/run_eval.py --quick      # Quick (10 questions)
    python evaluation/run_eval.py --output json
    python evaluation/run_eval.py --domain annual_leave

Outputs results to evaluation/results/YYYY-MM-DD_HH-MM/
Updates EVALUATION.md with latest metrics.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import argparse
from dataclasses import dataclass, field

from app.rag.retriever import HybridRetriever
from app.core.config import settings

# ── Evaluation Dataset ─────────────────────────────────────────────────────

@dataclass
class EvalQuestion:
    id: str
    question_ar: str
    question_en: str | None
    relevant_chunk_ids: list[str]
    gold_answer_ar: str
    domain: str
    difficulty: str  # easy | medium | hard


EVAL_QUESTIONS: list[EvalQuestion] = [
    EvalQuestion(
        id="eval_001",
        question_ar="كم عدد أيام الإجازة السنوية التي يحق للموظف الحصول عليها؟",
        question_en="How many annual leave days is an employee entitled to?",
        relevant_chunk_ids=["handbook_ch6_p34_0"],
        gold_answer_ar="يحق للموظف الحصول على 21 يوم عمل كإجازة سنوية مدفوعة الأجر",
        domain="annual_leave",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_002",
        question_ar="ما هي شروط استحقاق الإجازة السنوية الكاملة؟",
        question_en="What are the conditions for full annual leave entitlement?",
        relevant_chunk_ids=["handbook_ch6_p34_0", "handbook_ch6_p34_1"],
        gold_answer_ar="يستحق الموظف الإجازة السنوية الكاملة بعد اجتياز فترة الاختبار 90 يوماً",
        domain="annual_leave",
        difficulty="medium",
    ),
    EvalQuestion(
        id="eval_003",
        question_ar="كيف أتقدم بطلب إجازة سنوية؟",
        question_en="How do I apply for annual leave?",
        relevant_chunk_ids=["handbook_ch6_p34_0"],
        gold_answer_ar="يتقدم الموظف بطلب الإجازة عبر نظام الموارد البشرية الإلكتروني قبل 5 أيام عمل على الأقل",
        domain="annual_leave",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_004",
        question_ar="ما الفرق بين إجازة المرض العادية والممتدة؟",
        question_en="What is the difference between regular and extended sick leave?",
        relevant_chunk_ids=["handbook_ch6_p38_0", "handbook_ch6_p41_0"],
        gold_answer_ar="الإجازة العادية 30 يوم بأجر كامل، والممتدة حتى 180 يوم بأجر متدرج",
        domain="sick_leave",
        difficulty="medium",
    ),
    EvalQuestion(
        id="eval_005",
        question_ar="ما هي سياسة العمل عن بُعد؟",
        question_en="What is the remote work policy?",
        relevant_chunk_ids=["handbook_ch9_p58_0"],
        gold_answer_ar="يُسمح بالعمل عن بُعد بحد أقصى يومَين في الأسبوع بموافقة المدير",
        domain="remote_work",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_006",
        question_ar="ما هو التأمين الصحي الذي تقدمه الشركة؟",
        question_en="What health insurance does the company provide?",
        relevant_chunk_ids=["handbook_ch7_p54_0"],
        gold_answer_ar="توفر الشركة تأمين صحي شامل عبر بوبا العربية بخطط مختلفة حسب المستوى الوظيفي",
        domain="benefits",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_007",
        question_ar="كم مدة إجازة الأمومة؟",
        question_en="How long is maternity leave?",
        relevant_chunk_ids=["handbook_ch6_p44_0"],
        gold_answer_ar="إجازة الأمومة مدتها 70 يوم تقويمي بأجر كامل",
        domain="maternity_leave",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_008",
        question_ar="ما هي ميزانية التدريب السنوية للمهندسين؟",
        question_en="What is the annual training budget for engineers?",
        relevant_chunk_ids=["handbook_ch11_p75_0"],
        gold_answer_ar="المهندسون والمتخصصون يحصلون على 6,000 ريال سنوياً للتدريب",
        domain="professional_development",
        difficulty="medium",
    ),
    EvalQuestion(
        id="eval_009",
        question_ar="ما هي ساعات الدوام الرسمية؟",
        question_en="What are the official working hours?",
        relevant_chunk_ids=["handbook_ch10_p68_0"],
        gold_answer_ar="الدوام من الأحد إلى الخميس من 8 صباحاً إلى 5 مساءً بمعدل 40 ساعة أسبوعياً",
        domain="attendance",
        difficulty="easy",
    ),
    EvalQuestion(
        id="eval_010",
        question_ar="متى تُصرف رواتب الموظفين؟",
        question_en="When are employee salaries paid?",
        relevant_chunk_ids=["handbook_ch7_p50_0"],
        gold_answer_ar="يُصرف الراتب في اليوم الأخير من كل شهر ميلادي",
        domain="compensation",
        difficulty="easy",
    ),
]

# ── Metrics Computation ───────────────────────────────────────────────────

@dataclass
class QuestionResult:
    question_id: str
    domain: str
    retrieved_ids: list[str]
    relevant_ids: list[str]
    precision_at_k: dict[int, float] = field(default_factory=dict)
    recall_at_k: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Precision@K — fraction of top-K retrieved that are relevant."""
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / k if k > 0 else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Recall@K — fraction of relevant chunks in top-K."""
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / len(relevant) if relevant else 0.0


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """MRR — 1/rank of first relevant chunk."""
    for rank, chunk_id in enumerate(retrieved, 1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


# ── Evaluation Runner ─────────────────────────────────────────────────────

async def run_evaluation(
    questions: list[EvalQuestion],
    quick: bool = False,
) -> list[QuestionResult]:
    retriever = HybridRetriever()
    results = []

    sample = questions[:10] if quick else questions

    for q in sample:
        print(f"  [{q.id}] {q.question_ar[:50]}...")
        try:
            import time
            start = time.time()
            chunks = await retriever.retrieve(q.question_ar, top_k=5)
            latency = (time.time() - start) * 1000

            retrieved_ids = [c["metadata"].get("chunk_id", "") for c in chunks]
            relevant_set = set(q.relevant_chunk_ids)

            result = QuestionResult(
                question_id=q.id,
                domain=q.domain,
                retrieved_ids=retrieved_ids,
                relevant_ids=q.relevant_chunk_ids,
                latency_ms=latency,
            )

            for k in [1, 3, 5]:
                result.precision_at_k[k] = precision_at_k(retrieved_ids, relevant_set, k)
                result.recall_at_k[k] = recall_at_k(retrieved_ids, relevant_set, k)

            result.mrr = mean_reciprocal_rank(retrieved_ids, relevant_set)
            results.append(result)

            status = "✅" if result.precision_at_k[5] > 0 else "❌"
            print(f"     {status} P@5={result.precision_at_k[5]:.2f} MRR={result.mrr:.2f} ({latency:.0f}ms)")

        except Exception as e:
            results.append(QuestionResult(
                question_id=q.id,
                domain=q.domain,
                retrieved_ids=[],
                relevant_ids=q.relevant_chunk_ids,
                error=str(e),
            ))
            print(f"     ❌ Error: {e}")

    return results


def compute_aggregate_metrics(results: list[QuestionResult]) -> dict:
    valid = [r for r in results if r.error is None]
    if not valid:
        return {"error": "No valid results"}

    metrics = {}
    for k in [1, 3, 5]:
        metrics[f"precision_at_{k}"] = sum(r.precision_at_k.get(k, 0) for r in valid) / len(valid)
        metrics[f"recall_at_{k}"] = sum(r.recall_at_k.get(k, 0) for r in valid) / len(valid)

    metrics["mrr"] = sum(r.mrr for r in valid) / len(valid)
    metrics["avg_latency_ms"] = sum(r.latency_ms for r in valid) / len(valid)
    metrics["total_questions"] = len(results)
    metrics["errors"] = len(results) - len(valid)

    # Per-domain breakdown
    domains = {}
    for r in valid:
        if r.domain not in domains:
            domains[r.domain] = []
        domains[r.domain].append(r.precision_at_k.get(5, 0))

    metrics["by_domain"] = {
        domain: {"p5": sum(scores)/len(scores), "n": len(scores)}
        for domain, scores in domains.items()
    }

    return metrics


def print_summary(metrics: dict):
    print("\n" + "="*60)
    print("📊 RAG EVALUATION RESULTS")
    print("="*60)
    print(f"Questions evaluated: {metrics['total_questions']}")
    print(f"Errors: {metrics.get('errors', 0)}")
    print()
    print("Retrieval Metrics:")
    print(f"  Precision@1: {metrics['precision_at_1']:.3f}")
    print(f"  Precision@3: {metrics['precision_at_3']:.3f}")
    print(f"  Precision@5: {metrics['precision_at_5']:.3f}  {'✅' if metrics['precision_at_5'] >= 0.80 else '❌ (target: 0.80)'}")
    print(f"  Recall@5:    {metrics['recall_at_5']:.3f}")
    print(f"  MRR:         {metrics['mrr']:.3f}")
    print(f"  Avg Latency: {metrics['avg_latency_ms']:.0f}ms")
    print()
    print("By Domain:")
    for domain, stats in metrics.get("by_domain", {}).items():
        print(f"  {domain:30s} P@5={stats['p5']:.2f} (n={stats['n']})")
    print("="*60)


async def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation Runner")
    parser.add_argument("--quick", action="store_true", help="Run only first 10 questions")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--domain", type=str, help="Filter to specific domain")
    args = parser.parse_args()

    questions = EVAL_QUESTIONS
    if args.domain:
        questions = [q for q in questions if q.domain == args.domain]

    print(f"🔍 Running RAG evaluation ({len(questions)} questions)...")
    results = await run_evaluation(questions, quick=args.quick)
    metrics = compute_aggregate_metrics(results)

    if args.output == "json":
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print_summary(metrics)

    # Save results
    output_dir = Path(__file__).parent / "results" / datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2)
    )
    print(f"\n📁 Results saved to {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
