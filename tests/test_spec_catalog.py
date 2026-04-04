from pathlib import Path

import pytest

from faulthunter.case_bank import build_case_bank
from faulthunter.models import RunProfile
from faulthunter.spec_catalog import (
    MARKER_END,
    MARKER_START,
    extract_catalog_region,
    render_auto_catalog,
    splice_catalog,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_PATH = _REPO_ROOT / "specs" / "FEATURE_TEST_SPEC.md"


def test_on_disk_feature_spec_matches_rendered_catalog():
    """Drift guard: committed FEATURE_TEST_SPEC.md auto section must match case_bank."""
    text = _SPEC_PATH.read_text(encoding="utf-8")
    assert MARKER_START in text
    assert MARKER_END in text
    inner = extract_catalog_region(text)
    assert inner == render_auto_catalog().strip("\n")


def test_render_auto_catalog_covers_all_case_ids():
    body = render_auto_catalog()
    for profile in (RunProfile.SMOKE, RunProfile.DAILY):
        for c in build_case_bank(profile):
            assert c.id in body, f"missing case id {c.id}"


def test_splice_catalog_roundtrip():
    gen = render_auto_catalog()
    original = (
        "Preamble\n\n"
        + MARKER_START
        + "\nold\n"
        + MARKER_END
        + "\ntrailer\n"
    )
    updated = splice_catalog(original, gen)
    assert extract_catalog_region(updated) == gen.strip("\n")
    with pytest.raises(ValueError):
        extract_catalog_region("no markers")
