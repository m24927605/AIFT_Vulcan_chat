import json
import pytest
from pathlib import Path

def test_eval_dataset_is_valid_json():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    assert dataset_path.exists(), f"Missing eval dataset: {dataset_path}"
    data = json.loads(dataset_path.read_text())
    assert isinstance(data, list)
    assert len(data) >= 15

def test_eval_dataset_has_required_fields():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    data = json.loads(dataset_path.read_text())
    for i, case in enumerate(data):
        assert "query" in case, f"Case {i} missing 'query'"
        assert "expected_needs_search" in case, f"Case {i} missing 'expected_needs_search'"
        assert "expected_query_type" in case, f"Case {i} missing 'expected_query_type'"
        assert "category" in case, f"Case {i} missing 'category'"
        assert isinstance(case["expected_needs_search"], bool)

def test_eval_dataset_covers_all_categories():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    data = json.loads(dataset_path.read_text())
    categories = {case["category"] for case in data}
    required = {"temporal", "factual", "conversational", "greeting", "math", "tw_stock", "us_stock", "forex"}
    assert required.issubset(categories), f"Missing categories: {required - categories}"
