"""SO1 / SO3: automated inline checks and bill day-count helper."""

from datetime import datetime, timezone
from app.services import pricing_service as pricing
from app.services.prescription_service import run_automated_checks

# Bed-day count is at least 1 and counts whole days.
def test_days_between_minimum_one():
    start = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
    same = datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc)
    assert pricing._days_between(start, same) == 1
    
def test_days_between_multiple_days():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 4, tzinfo=timezone.utc)
    assert pricing._days_between(start, end) == 3

# The default catalogue includes the core billable items.
def test_default_catalogue_has_core_items():
    codes = {i["code"] for i in pricing.DEFAULT_CATALOGUE}
    for required in ("consultation_opd", "bed_general", "nursing_care", "medication_default"):
        assert required in codes

# Inline automated check flags an obviously high dose.
def test_inline_check_flags_high_dose():
    rx = {"medications": [{"name": "DrugX", "dose": "5000mg", "duration_days": 5}]}
    issues = run_automated_checks(rx)
    assert any(i["flag_code"] == "high_dose" for i in issues)

# A normal dose produces no inline high-dose flag.
def test_inline_check_normal_dose_clean():
    rx = {"medications": [{"name": "DrugX", "dose": "500mg", "duration_days": 5}]}
    issues = run_automated_checks(rx)
    assert not any(i["flag_code"] == "high_dose" for i in issues)
