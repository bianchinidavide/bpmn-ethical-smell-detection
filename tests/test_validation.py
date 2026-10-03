"""Unit tests for the output validation and Pydantic schema enforcement module.

Verifies:
1. Deserialization and validation of model responses into the ReportEtico schema.
2. Rejection of unexpected/hallucinated JSON keys via Pydantic extra="forbid" (ValidationError).
3. Referential integrity filtering against real diagram node IDs and official Knowledge Base smell codes.
"""

import json
import pytest
from pydantic import ValidationError

from services.auditor import (
    ReportEtico,
    Violazione,
    filter_referential_integrity,
)


# 1. schema validation tests
def test_valid_report_etico_deserialization():
    """Verify that a compliant JSON payload is parsed into ReportEtico properly."""
    payload = {
        "violazioni": [
            {
                "id_nodo": "Activity_1g8a9v6",
                "codice_smell": "ES-19",
                "spiegazione": "L'algoritmo valuta lo scoring senza supervisione umana."
            }
        ]
    }
    report = ReportEtico.model_validate_json(json.dumps(payload))
    assert len(report.violazioni) == 1
    assert report.violazioni[0].id_nodo == "Activity_1g8a9v6"
    assert report.violazioni[0].codice_smell == "ES-19"
    assert "supervisione umana" in report.violazioni[0].spiegazione


def test_empty_violations_represents_compliant_process():
    """Verify that an empty violations array validates as a compliant audit result."""
    payload = {"violazioni": []}
    report = ReportEtico.model_validate_json(json.dumps(payload))
    assert len(report.violazioni) == 0
    assert isinstance(report.violazioni, list)


def test_missing_required_fields_raises_validation_error():
    """Verify that omitting a mandatory field (e.g., id_nodo) triggers a ValidationError."""
    incomplete_payload = {
        "violazioni": [
            {
                "codice_smell": "ES-19",
                "spiegazione": "Manca l'ID del nodo."
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ReportEtico.model_validate_json(json.dumps(incomplete_payload))
    assert "id_nodo" in str(exc_info.value)


# 2. extra="forbid" constraint tests to prevent structural hallucinations
def test_extra_field_in_violation_raises_validation_error():
    """Verify that extra="forbid" rejects payloads containing unexpected violation fields."""
    hallucinated_payload = {
        "violazioni": [
            {
                "id_nodo": "Task_1",
                "codice_smell": "ES-19",
                "spiegazione": "Spiegazione valida.",
                "confidence_score": 0.98  # unexpected extra property
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ReportEtico.model_validate_json(json.dumps(hallucinated_payload))
    assert "extra_forbidden" in str(exc_info.value) or "confidence_score" in str(exc_info.value)


def test_extra_root_field_raises_validation_error():
    """Verify that extra="forbid" rejects payloads with hallucinated root-level keys."""
    hallucinated_root_payload = {
        "violazioni": [],
        "overall_ethical_risk": "HIGH"  # unexpected extra root property
    }
    with pytest.raises(ValidationError) as exc_info:
        ReportEtico.model_validate_json(json.dumps(hallucinated_root_payload))
    assert "extra_forbidden" in str(exc_info.value) or "overall_ethical_risk" in str(exc_info.value)


# 3. referential integrity filtering tests
def test_referential_integrity_filter_discards_hallucinated_ids():
    """Verify that violations referencing non-existent nodes or smell codes are discarded."""
    # define ground truth sets from diagram and knowledge base
    valid_bpmn_nodes = {"Activity_Scoring", "Activity_Review"}
    valid_kb_smells = {"ES-01", "ES-19"}

    raw_report = ReportEtico(
        violazioni=[
            # 1. fully valid violation
            Violazione(
                id_nodo="Activity_Scoring",
                codice_smell="ES-19",
                spiegazione="Supervisione umana assente."
            ),
            # 2. hallucinated node id (not in bpmn diagram)
            Violazione(
                id_nodo="Activity_Invented_999",
                codice_smell="ES-19",
                spiegazione="Nodo inventato dal modello."
            ),
            # 3. hallucinated smell code (not in knowledge base)
            Violazione(
                id_nodo="Activity_Review",
                codice_smell="ES-999_FAKE",
                spiegazione="Codice smell inesistente."
            )
        ]
    )

    filtered_report = filter_referential_integrity(
        report=raw_report,
        valid_node_ids=valid_bpmn_nodes,
        valid_smell_codes=valid_kb_smells
    )

    # only the first violation should be retained
    assert len(filtered_report.violazioni) == 1
    assert filtered_report.violazioni[0].id_nodo == "Activity_Scoring"
    assert filtered_report.violazioni[0].codice_smell == "ES-19"


def test_referential_integrity_all_invalid_yields_empty_report():
    """Verify that if all reported violations are hallucinated, the result is empty."""
    valid_bpmn_nodes = {"Activity_Real"}
    valid_kb_smells = {"ES-01"}

    raw_report = ReportEtico(
        violazioni=[
            Violazione(
                id_nodo="Fake_Node_1",
                codice_smell="ES-99",
                spiegazione="Entrambi i campi sono inventati."
            )
        ]
    )

    filtered = filter_referential_integrity(
        report=raw_report,
        valid_node_ids=valid_bpmn_nodes,
        valid_smell_codes=valid_kb_smells
    )
    assert len(filtered.violazioni) == 0
