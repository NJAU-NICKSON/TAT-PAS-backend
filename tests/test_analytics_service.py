"""
Unit tests for analytics_service.py helper functions
SO4 / RQ4 — verifies TAT calculation logic answers RQ1 (delay identification)
"""

import pytest
from app.services.analytics_service import _safe_avg, _calc_p95


# TC-16: Average of normal list
def test_safe_avg_normal():
    assert _safe_avg([10.0, 20.0, 30.0]) == 20.0


# TC-17: None values are excluded from average
def test_safe_avg_excludes_none():
    assert _safe_avg([10.0, None, 30.0]) == 20.0


# TC-18: Empty list returns 0.0
def test_safe_avg_empty():
    assert _safe_avg([]) == 0.0


# TC-19: All None values returns 0.0
def test_safe_avg_all_none():
    assert _safe_avg([None, None]) == 0.0


# TC-20: P95 returns correct 95th percentile value
def test_calc_p95_correct():
    values = list(range(1, 101))  # 1 to 100
    # idx = int(100 * 0.95) = 95 → values[95] = 96
    result = _calc_p95(values)
    assert result == 96.0


# TC-21: P95 of single value returns that value
def test_calc_p95_single():
    assert _calc_p95([42.0]) == 42.0


# TC-22: P95 of empty list returns 0.0
def test_calc_p95_empty():
    assert _calc_p95([]) == 0.0
