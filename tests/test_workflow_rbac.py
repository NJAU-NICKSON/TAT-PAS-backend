"""SO3: role-based prescription workflow and accountability."""

from app.services.prescription_service import PERMITTED_TRANSITIONS


def _roles(from_status, to_status):
    return PERMITTED_TRANSITIONS.get(from_status, {}).get(to_status, [])


# Only the auditor verifies a submitted prescription (not pharmacist/doctor).
def test_only_auditor_verifies():
    roles = _roles("submitted", "verified")
    assert roles == ["auditor"]
    assert "pharmacist" not in roles
    assert "doctor" not in roles


# Only the pharmacist dispenses a verified prescription.
def test_only_pharmacist_dispenses():
    roles = _roles("verified", "dispensed")
    assert roles == ["pharmacist"]
    assert "auditor" not in roles


# Only the nurse administers a dispensed prescription.
def test_only_nurse_administers():
    roles = _roles("dispensed", "administered")
    assert roles == ["nurse"]


# The auditor (not the pharmacist) can return a prescription for amendment.
def test_auditor_returns_for_amendment():
    roles = _roles("submitted", "pending_amendment")
    assert roles == ["auditor"]


# The prescribing doctor resubmits after amendment.
def test_doctor_resubmits_after_amendment():
    assert "doctor" in _roles("pending_amendment", "submitted")


# A pharmacist cannot dispense something straight from 'submitted' (must be verified first).
def test_no_dispense_before_verify():
    assert _roles("submitted", "dispensed") == []


# Admin is not listed as a clinical actor in any transition (admin observes).
def test_admin_not_a_clinical_actor():
    for from_status, targets in PERMITTED_TRANSITIONS.items():
        for to_status, roles in targets.items():
            assert "admin" not in roles, f"admin should not act on {from_status}->{to_status}"
