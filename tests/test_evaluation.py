"""Harness unit tests; held-out repositories are not regression tests."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "doctor_evaluation", Path(__file__).parents[1] / "scripts/evaluate.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_metrics_keep_denominators_and_undefined_values():
    rows = [
        {
            "labels": [
                {"rule": "references/finding", "expected": expected, "observed": observed}
                for expected, observed in [
                    (True, True),
                    (True, False),
                    (False, True),
                    (False, False),
                ]
            ]
        }
    ]
    result = evaluation.measure(rows)["references/finding"]
    assert result == {
        "tp": 1,
        "fp": 1,
        "tn": 1,
        "fn": 1,
        "precision": 0.5,
        "recall": 0.5,
        "false_positive_rate": 0.5,
        "labeled_assertions": 4,
    }
    assert evaluation.measure([]) == {}
    assert (
        evaluation.measure(
            [{"labels": [{"rule": "negative", "expected": False, "observed": False}]}]
        )["negative"]["recall"]
        is None
    )
