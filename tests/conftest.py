"""
Shared fixtures for TAT-PAS test suite.
"""

import pytest


@pytest.fixture
def sample_patient():
    return {
        "allergies": [],
        "is_paediatric": False,
        "is_neonate": False,
        "is_pregnant": False,
        "weight_kg": 70,
    }


@pytest.fixture
def patient_with_penicillin_allergy(sample_patient):
    return {**sample_patient, "allergies": [{"substance": "Penicillin", "severity": "severe"}]}


@pytest.fixture
def paediatric_patient(sample_patient):
    return {**sample_patient, "is_paediatric": True, "weight_kg": 20}


@pytest.fixture
def neonatal_patient(sample_patient):
    return {**sample_patient, "is_neonate": True, "weight_kg": 3}


@pytest.fixture
def pregnant_patient(sample_patient):
    return {**sample_patient, "is_pregnant": True}


@pytest.fixture
def basic_medication():
    return {
        "name": "Amoxicillin",
        "dose": "500mg",
        "route": "oral",
        "frequency": "TDS",
        "duration_days": 7,
    }
