"""Accuracy measurement for syllabus extraction against ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class AccuracyResult:
    """Result of comparing extraction output to ground truth."""

    field_accuracy: float
    date_accuracy: float
    assessment_count_match: bool
    grade_total_accuracy: float
    fields_checked: int
    fields_correct: int
    dates_checked: int
    dates_correct: int


def _normalize(text: str | None) -> str:
    """Lowercase, strip whitespace and punctuation for fuzzy matching."""
    if text is None:
        return ""
    return text.lower().strip().rstrip(".")


def _fuzzy_match(extracted: str | None, expected: str | None) -> bool:
    """Check if extracted value matches expected with fuzzy tolerance."""
    if expected is None:
        return True  # don't penalize optional fields
    e = _normalize(extracted)
    x = _normalize(expected)
    if not e or not x:
        return False
    # Exact match or substring containment (either direction)
    return e == x or x in e or e in x


def _weight_match(
    extracted: float | str | None, expected: float | None, tolerance: float = 2.0
) -> bool:
    """Check if weight_percent matches within tolerance."""
    if expected is None:
        return True
    try:
        ext = float(extracted) if extracted is not None else None
    except (ValueError, TypeError):
        return False
    if ext is None:
        return False
    return abs(ext - expected) <= tolerance


def _date_match(
    extracted: str | None, expected: str | None, tolerance_days: int = 1
) -> bool:
    """Check if dates match within tolerance (to handle off-by-one)."""
    if expected is None:
        return True
    if extracted is None:
        return False
    try:
        ext_date = date.fromisoformat(str(extracted))
        exp_date = date.fromisoformat(str(expected))
    except (ValueError, TypeError):
        return False
    return abs((ext_date - exp_date).days) <= tolerance_days


def _extract_field_value(extraction: dict, key: str) -> str | None:
    """Get the value from an ExtractedField dict or plain value."""
    field = extraction.get(key)
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return str(field)


def _get_assessments(extraction: dict) -> list[dict]:
    """Get assessments list from extraction, handling nested structure."""
    return extraction.get("assessments", [])


def _get_field(assessment: dict, key: str) -> str | float | None:
    """Get a field value from an assessment, handling ExtractedField wrapping."""
    field = assessment.get(key)
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return field


def _find_best_match(
    gt_assessment: dict, extracted: list[dict]
) -> dict | None:
    """Find the extracted assessment that best matches the ground truth one."""
    gt_title = _normalize(gt_assessment.get("title", ""))
    if not gt_title:
        return None

    best = None
    best_score = 0
    for ext in extracted:
        ext_title = _normalize(_get_field(ext, "title"))
        if not ext_title:
            continue
        # Score by title similarity
        score = 0
        if ext_title == gt_title:
            score = 3
        elif gt_title in ext_title or ext_title in gt_title:
            score = 2
        elif set(gt_title.split()) & set(ext_title.split()):
            score = 1

        if score > best_score:
            best_score = score
            best = ext

    return best if best_score > 0 else None


def _grade_total_accuracy(extraction: dict) -> float:
    """How close the grade breakdown total is to 100%."""
    breakdown = extraction.get("grade_breakdown", [])
    total = 0.0
    for comp in breakdown:
        weight = comp.get("weight_percent")
        if isinstance(weight, dict):
            weight = weight.get("value")
        try:
            total += float(weight) if weight is not None else 0.0
        except (ValueError, TypeError):
            pass
    if total == 0:
        return 0.0
    return max(0.0, 1.0 - abs(total - 100.0) / 100.0)


def compute_accuracy(extraction: dict, ground_truth: dict) -> AccuracyResult:
    """Compare extraction output against ground truth.

    Checks:
    - Top-level fields: course_name, course_code, instructor_name
    - Assessment count
    - Each assessment: title match (fuzzy), type match, weight (within 2%)
    - Each assessment: date match (exact or within 1 day)
    - Grade breakdown total (within 2% of 100)
    """
    fields_checked = 0
    fields_correct = 0
    dates_checked = 0
    dates_correct = 0

    # Top-level field checks
    for field_key in ["course_name", "course_code", "instructor_name"]:
        if field_key in ground_truth and ground_truth[field_key] is not None:
            fields_checked += 1
            extracted_value = _extract_field_value(extraction, field_key)
            if _fuzzy_match(extracted_value, ground_truth[field_key]):
                fields_correct += 1

    # Assessment matching
    gt_assessments = ground_truth.get("assessments", [])
    ext_assessments = _get_assessments(extraction)

    assessment_count_match = len(ext_assessments) == len(gt_assessments)

    for gt_a in gt_assessments:
        match = _find_best_match(gt_a, ext_assessments)
        if match is None:
            # Count all fields as missed
            fields_checked += 3  # title, type, weight
            if gt_a.get("due_date"):
                dates_checked += 1
            continue

        # Check title
        fields_checked += 1
        if _fuzzy_match(_get_field(match, "title"), gt_a.get("title")):
            fields_correct += 1

        # Check type
        fields_checked += 1
        if _fuzzy_match(_get_field(match, "type"), gt_a.get("type")):
            fields_correct += 1

        # Check weight
        fields_checked += 1
        if _weight_match(
            _get_field(match, "weight_percent"),
            gt_a.get("weight_percent"),
        ):
            fields_correct += 1

        # Check date
        if gt_a.get("due_date") is not None:
            dates_checked += 1
            resolved = _get_field(match, "due_date_resolved") or _get_field(
                match, "due_date"
            )
            if _date_match(resolved, gt_a["due_date"]):
                dates_correct += 1

    return AccuracyResult(
        field_accuracy=fields_correct / max(fields_checked, 1),
        date_accuracy=dates_correct / max(dates_checked, 1),
        assessment_count_match=assessment_count_match,
        grade_total_accuracy=_grade_total_accuracy(extraction),
        fields_checked=fields_checked,
        fields_correct=fields_correct,
        dates_checked=dates_checked,
        dates_correct=dates_correct,
    )
