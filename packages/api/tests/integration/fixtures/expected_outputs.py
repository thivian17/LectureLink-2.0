"""Ground-truth data for accuracy measurement.

Each dict provides the expected extraction results for a test syllabus,
keyed by syllabus name matching syllabus_generator.ALL_SYLLABI.
"""

from __future__ import annotations

from tests.integration.fixtures.syllabus_generator import (
    build_business_syllabus,
    build_docx_syllabus,
    build_minimal_syllabus,
    build_stem_syllabus,
    build_week_format_syllabus,
)

# Ground truths are embedded in each generator's return value.
# This module provides convenient access to just the ground-truth dicts.

_, _, STEM_TRUTH = build_stem_syllabus()
_, _, BUSINESS_TRUTH = build_business_syllabus()
_, _, MINIMAL_TRUTH = build_minimal_syllabus()
_, _, WEEK_FORMAT_TRUTH = build_week_format_syllabus()
_, _, DOCX_TRUTH = build_docx_syllabus()

ALL_TRUTHS = {
    "stem": STEM_TRUTH,
    "business": BUSINESS_TRUTH,
    "minimal": MINIMAL_TRUTH,
    "week_format": WEEK_FORMAT_TRUTH,
    "docx": DOCX_TRUTH,
}
