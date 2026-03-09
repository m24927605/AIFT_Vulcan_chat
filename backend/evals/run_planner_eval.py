"""
Offline evaluation runner for PlannerAgent.
Usage:
  python -m evals.run_planner_eval              # uses real LLM (needs API key)
  python -m evals.run_planner_eval --dry-run    # prints dataset stats only
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path


def load_dataset() -> list[dict]:
    path = Path(__file__).parent / "planner_eval_dataset.json"
    return json.loads(path.read_text())


def score_results(dataset: list[dict], results: list[dict]) -> dict:
    total = len(dataset)
    needs_search_correct = 0
    query_type_correct = 0
    data_source_correct = 0
    data_source_total = 0
    failures = []

    for case, result in zip(dataset, results):
        if result.get("needs_search") == case["expected_needs_search"]:
            needs_search_correct += 1
        else:
            failures.append({
                "query": case["query"],
                "field": "needs_search",
                "expected": case["expected_needs_search"],
                "actual": result.get("needs_search"),
            })
        if result.get("query_type") == case["expected_query_type"]:
            query_type_correct += 1
        if "expected_data_source_type" in case:
            data_source_total += 1
            actual_types = [ds.get("type") for ds in result.get("data_sources", [])]
            if case["expected_data_source_type"] in actual_types:
                data_source_correct += 1

    return {
        "total": total,
        "needs_search_accuracy": needs_search_correct / total if total else 0,
        "query_type_accuracy": query_type_correct / total if total else 0,
        "data_source_accuracy": data_source_correct / data_source_total if data_source_total else 0,
        "failures": failures,
    }


async def run_eval() -> None:
    dataset = load_dataset()

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        categories = {}
        for case in dataset:
            cat = case["category"]
            categories[cat] = categories.get(cat, 0) + 1
        print(f"Dataset: {len(dataset)} cases")
        print(f"Categories: {json.dumps(categories, indent=2)}")
        return

    from app.core.config import settings
    from app.core.services.llm_factory import create_llm_client
    from app.core.agents.planner import PlannerAgent

    llm = create_llm_client(settings)
    planner = PlannerAgent(llm=llm)

    results = []
    for i, case in enumerate(dataset):
        print(f"[{i+1}/{len(dataset)}] {case['query'][:50]}...")
        decision = await planner.plan(case["query"])
        results.append({
            "needs_search": decision.needs_search,
            "query_type": decision.query_type,
            "data_sources": [
                {"type": ds.type, "symbol": ds.symbol}
                for ds in decision.data_sources
            ],
            "reasoning": decision.reasoning,
        })

    scores = score_results(dataset, results)
    print(f"\n=== Planner Evaluation Results ===")
    print(f"Total cases: {scores['total']}")
    print(f"needs_search accuracy: {scores['needs_search_accuracy']:.1%}")
    print(f"query_type accuracy:   {scores['query_type_accuracy']:.1%}")
    print(f"data_source accuracy:  {scores['data_source_accuracy']:.1%}")

    if scores["failures"]:
        print(f"\nFailures ({len(scores['failures'])}):")
        for f in scores["failures"]:
            print(f"  - {f['query']}: expected {f['field']}={f['expected']}, got {f['actual']}")


if __name__ == "__main__":
    asyncio.run(run_eval())
