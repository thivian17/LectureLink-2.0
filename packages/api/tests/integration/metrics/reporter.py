"""Metrics collection and reporting for E2E tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .accuracy import AccuracyResult


@dataclass
class SyllabusMetrics:
    name: str
    accuracy: AccuracyResult
    processing_time_seconds: float
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


class MetricsReporter:
    """Collects metrics from E2E runs and writes a summary report."""

    def __init__(self):
        self._results: list[SyllabusMetrics] = []

    def record(
        self, name: str, accuracy: AccuracyResult, time_s: float
    ) -> None:
        self._results.append(SyllabusMetrics(name, accuracy, time_s))

    @property
    def results(self) -> list[SyllabusMetrics]:
        return list(self._results)

    def summary(self) -> dict:
        if not self._results:
            return {"error": "no results"}

        avg_field = sum(
            r.accuracy.field_accuracy for r in self._results
        ) / len(self._results)
        avg_date = sum(
            r.accuracy.date_accuracy for r in self._results
        ) / len(self._results)
        avg_time = sum(
            r.processing_time_seconds for r in self._results
        ) / len(self._results)

        return {
            "syllabi_tested": len(self._results),
            "avg_field_accuracy": round(avg_field, 4),
            "avg_date_accuracy": round(avg_date, 4),
            "avg_processing_time_s": round(avg_time, 2),
            "pass_criteria": {
                "all_pass_70pct_field": all(
                    r.accuracy.field_accuracy >= 0.7 for r in self._results
                ),
                "all_pass_90pct_date": all(
                    r.accuracy.date_accuracy >= 0.9 for r in self._results
                ),
                "all_under_60s": all(
                    r.processing_time_seconds < 60
                    for r in self._results
                ),
            },
            "details": [
                {
                    "name": r.name,
                    "field_accuracy": round(r.accuracy.field_accuracy, 4),
                    "date_accuracy": round(r.accuracy.date_accuracy, 4),
                    "fields": f"{r.accuracy.fields_correct}/{r.accuracy.fields_checked}",
                    "dates": f"{r.accuracy.dates_correct}/{r.accuracy.dates_checked}",
                    "assessment_count_match": r.accuracy.assessment_count_match,
                    "grade_total_accuracy": round(
                        r.accuracy.grade_total_accuracy, 4
                    ),
                    "time_s": round(r.processing_time_seconds, 2),
                }
                for r in self._results
            ],
        }

    def write_report(self, path: Path | None = None) -> Path:
        path = path or Path("test_metrics_report.json")
        path.write_text(json.dumps(self.summary(), indent=2))
        return path
