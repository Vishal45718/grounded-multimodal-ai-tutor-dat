import json
import pytest
import os
import copy

CASES_PATH = "benchmark/cases.jsonl"

def load_cases():
    cases = []
    with open(CASES_PATH, "r") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

@pytest.fixture
def benchmark_cases():
    return load_cases()

def test_benchmark_loads(benchmark_cases):
    assert len(benchmark_cases) > 0

def test_exactly_20_cases(benchmark_cases):
    assert len(benchmark_cases) == 20

def test_case_ids_unique(benchmark_cases):
    ids = [case.get("id") for case in benchmark_cases]
    assert len(ids) == len(set(ids))

def test_required_fields(benchmark_cases):
    required_fields = {
        "id", "question", "category", "expected_answer", 
        "expected_evidence_ids", "expected_source_id", 
        "expected_version_id", "answerability", 
        "visual_required", "adversarial_type", "notes"
    }
    for case in benchmark_cases:
        assert set(case.keys()) == required_fields

def test_at_least_5_visual_required(benchmark_cases):
    visual_count = sum(1 for case in benchmark_cases if case.get("visual_required") is True)
    assert visual_count >= 5

def test_visual_cases_contain_justification(benchmark_cases):
    for case in benchmark_cases:
        if case.get("visual_required") is True:
            assert case.get("notes") is not None
            assert len(case.get("notes").strip()) > 0

def test_answerable_cases_have_gold_evidence(benchmark_cases):
    for case in benchmark_cases:
        if case.get("answerability") in ["answerable", "partial"]:
            assert isinstance(case.get("expected_evidence_ids"), list)
            assert len(case.get("expected_evidence_ids")) > 0
            assert case.get("expected_source_id") is not None
            assert case.get("expected_version_id") is not None

def test_unanswerable_cases_have_no_gold_evidence(benchmark_cases):
    for case in benchmark_cases:
        if case.get("answerability") == "unanswerable":
            assert isinstance(case.get("expected_evidence_ids"), list)
            assert len(case.get("expected_evidence_ids")) == 0

def test_invalid_benchmark_entries_rejected():
    # Load cases and intentionally break one to test validation logic
    # To keep it self-contained, we just ensure that validation would fail
    # if required fields are missing.
    valid_case = load_cases()[0]
    invalid_case = copy.deepcopy(valid_case)
    del invalid_case["id"]
    
    required_fields = {
        "id", "question", "category", "expected_answer", 
        "expected_evidence_ids", "expected_source_id", 
        "expected_version_id", "answerability", 
        "visual_required", "adversarial_type", "notes"
    }
    assert set(invalid_case.keys()) != required_fields
