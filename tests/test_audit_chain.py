"""SO4 / RQ4: tamper-evident audit trail (SHA-256 hash chain)."""

from datetime import datetime, timezone
from app.services.audit_service import compute_record_hash, GENESIS_HASH


def _record(issue, n):
    return {
        "prescription_id": f"rx{n}",
        "type": "status_change",
        "issue": issue,
        "severity": "low",
        "created_by": "u1",
        "created_at": datetime(2026, 6, 1, 8, n, tzinfo=timezone.utc),
    }


# The same record + prev_hash always produces the same hash (deterministic).
def test_hash_is_deterministic():
    rec = _record("status changed", 1)
    h1 = compute_record_hash(rec, GENESIS_HASH)
    h2 = compute_record_hash(rec, GENESIS_HASH)
    assert h1 == h2
    assert len(h1) == 64


# Changing any content changes the hash (tamper is detectable).
def test_tampering_changes_hash():
    rec = _record("status changed", 1)
    original = compute_record_hash(rec, GENESIS_HASH)
    rec["issue"] = "status changed (TAMPERED)"
    assert compute_record_hash(rec, GENESIS_HASH) != original


# Each record chains to the previous hash; recomputation verifies the chain.
def test_chain_links_and_verifies():
    records = [_record(f"event {i}", i) for i in range(1, 6)]
    prev = GENESIS_HASH
    for r in records:
        r["prev_hash"] = prev
        r["record_hash"] = compute_record_hash(r, prev)
        prev = r["record_hash"]

    # Independent verification pass.
    prev = GENESIS_HASH
    intact = True
    for r in records:
        if r["prev_hash"] != prev or r["record_hash"] != compute_record_hash(r, prev):
            intact = False
        prev = r["record_hash"]
    assert intact


# Tampering with a middle record breaks the chain from that point on.
def test_tampering_breaks_chain():
    records = [_record(f"event {i}", i) for i in range(1, 6)]
    prev = GENESIS_HASH
    for r in records:
        r["prev_hash"] = prev
        r["record_hash"] = compute_record_hash(r, prev)
        prev = r["record_hash"]

    records[2]["issue"] = "secretly altered"  # tamper without recomputing hashes

    prev = GENESIS_HASH
    broken = 0
    for r in records:
        if r["record_hash"] != compute_record_hash(r, prev):
            broken += 1
        prev = r["record_hash"]
    assert broken >= 1
