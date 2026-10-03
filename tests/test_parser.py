"""Unit tests for the BPMN 2.0 parser and topological linearizer module.

Verifies:
1. Causal order reconstruction via BFS traversal, including branches and parallel flows.
2. Organizational role/lane mapping inheritance across process tasks.
3. Fault tolerance against malformed XML, invalid namespaces, and missing process tags.
"""

from pathlib import Path
import pytest

from services.bpmn_parser import (
    BPMNParserError,
    extract_connections_and_adjacency,
    extract_lane_mappings,
    extract_nodes,
    linearize_bpmn_bfs,
    parse_bpmn_to_text,
)


# sample bpmn fixtures
SAMPLE_BRANCHING_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_Branching" isExecutable="true">
    <startEvent id="Start_1" name="Richiesta Ricevuta" />
    <exclusiveGateway id="Gateway_Split" name="Verifica Requisiti" />
    <task id="Task_Approved" name="Elabora Approvazione" />
    <task id="Task_Rejected" name="Invia Notifica Rifiuto" />
    <exclusiveGateway id="Gateway_Join" name="Confluenza" />
    <endEvent id="End_1" name="Fine Procedura" />

    <sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Gateway_Split" />
    <sequenceFlow id="Flow_2" name="Idoneo" sourceRef="Gateway_Split" targetRef="Task_Approved" />
    <sequenceFlow id="Flow_3" name="Non Idoneo" sourceRef="Gateway_Split" targetRef="Task_Rejected" />
    <sequenceFlow id="Flow_4" sourceRef="Task_Approved" targetRef="Gateway_Join" />
    <sequenceFlow id="Flow_5" sourceRef="Task_Rejected" targetRef="Gateway_Join" />
    <sequenceFlow id="Flow_6" sourceRef="Gateway_Join" targetRef="End_1" />
  </process>
</definitions>
"""

SAMPLE_PARALLEL_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_Parallel" isExecutable="true">
    <startEvent id="Start_P" name="Avvio Pratica" />
    <parallelGateway id="Fork_1" name="Sdoppia Controlli" />
    <task id="Task_CheckCredit" name="Controllo Creditizio" />
    <task id="Task_CheckIdentity" name="Verifica Identità" />
    <parallelGateway id="Join_1" name="Attendi Controlli" />
    <endEvent id="End_P" name="Pratica Evasa" />

    <sequenceFlow id="f1" sourceRef="Start_P" targetRef="Fork_1" />
    <sequenceFlow id="f2" sourceRef="Fork_1" targetRef="Task_CheckCredit" />
    <sequenceFlow id="f3" sourceRef="Fork_1" targetRef="Task_CheckIdentity" />
    <sequenceFlow id="f4" sourceRef="Task_CheckCredit" targetRef="Join_1" />
    <sequenceFlow id="f5" sourceRef="Task_CheckIdentity" targetRef="Join_1" />
    <sequenceFlow id="f6" sourceRef="Join_1" targetRef="End_P" />
  </process>
</definitions>
"""

SAMPLE_LANES_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             targetNamespace="http://bpmn.io/schema/bpmn">
  <process id="Process_Lanes" isExecutable="true">
    <laneSet id="LaneSet_1">
      <lane id="Lane_HR" name="Responsabile Risorse Umane">
        <flowNodeRef>Task_HR_Review</flowNodeRef>
      </lane>
      <lane id="Lane_AI" name="Algoritmo Valutazione">
        <flowNodeRef>Task_AI_Score</flowNodeRef>
      </lane>
    </laneSet>

    <startEvent id="Start_L" name="Candidatura" />
    <task id="Task_AI_Score" name="Calcolo Scoring Automatico" />
    <task id="Task_HR_Review" name="Revisione Dossier" />
    <endEvent id="End_L" name="Esito Notificato" />

    <sequenceFlow id="fl1" sourceRef="Start_L" targetRef="Task_AI_Score" />
    <sequenceFlow id="fl2" sourceRef="Task_AI_Score" targetRef="Task_HR_Review" />
    <sequenceFlow id="fl3" sourceRef="Task_HR_Review" targetRef="End_L" />
  </process>
</definitions>
"""


# 1. topological and bfs traversal tests
def test_bfs_reconstructs_causal_sequence_with_branches():
    """Verify that BFS linearization respects causal execution order in branching flows."""
    parsed_output = parse_bpmn_to_text(SAMPLE_BRANCHING_BPMN, is_file=False)

    # start event must appear before the split gateway
    idx_start = parsed_output.find("NODO [Start_1]")
    idx_split = parsed_output.find("NODO [Gateway_Split]")
    idx_approved = parsed_output.find("NODO [Task_Approved]")
    idx_rejected = parsed_output.find("NODO [Task_Rejected]")
    idx_join = parsed_output.find("NODO [Gateway_Join]")
    idx_end = parsed_output.find("NODO [End_1]")

    assert idx_start < idx_split, "Start event must precede the split gateway"
    assert idx_split < idx_approved, "Split gateway must precede the approved task"
    assert idx_split < idx_rejected, "Split gateway must precede the rejected task"
    assert idx_approved < idx_join, "Branch tasks must precede join gateway"
    assert idx_rejected < idx_join, "Branch tasks must precede join gateway"
    assert idx_join < idx_end, "Join gateway must precede end event"


def test_bfs_reconstructs_causal_sequence_with_parallel_flows():
    """Verify that BFS linearization handles parallel gateway forks and joins correctly."""
    parsed_output = parse_bpmn_to_text(SAMPLE_PARALLEL_BPMN, is_file=False)

    idx_start = parsed_output.find("NODO [Start_P]")
    idx_fork = parsed_output.find("NODO [Fork_1]")
    idx_credit = parsed_output.find("NODO [Task_CheckCredit]")
    idx_identity = parsed_output.find("NODO [Task_CheckIdentity]")
    idx_join = parsed_output.find("NODO [Join_1]")
    idx_end = parsed_output.find("NODO [End_P]")

    assert idx_start < idx_fork < idx_join < idx_end
    assert idx_fork < idx_credit < idx_join
    assert idx_fork < idx_identity < idx_join


# 2. organizational lane inheritance tests
def test_task_inherits_lane_actor_properly():
    """Verify that each process task correctly inherits the actor assigned to its lane."""
    parsed_output = parse_bpmn_to_text(SAMPLE_LANES_BPMN, is_file=False)

    # ai task must inherit the algorithm role
    assert "NODO [Task_AI_Score]: 'Calcolo Scoring Automatico'" in parsed_output
    assert "Eseguito da (Corsia/Ruolo): Algoritmo Valutazione" in parsed_output

    # hr task must inherit the human hr manager role
    assert "NODO [Task_HR_Review]: 'Revisione Dossier'" in parsed_output
    assert "Eseguito da (Corsia/Ruolo): Responsabile Risorse Umane" in parsed_output


def test_unassigned_node_gets_default_lane_fallback():
    """Verify that nodes without an explicit lane receive a general fallback label."""
    parsed_output = parse_bpmn_to_text(SAMPLE_LANES_BPMN, is_file=False)
    # start event Start_L was not assigned to any lane
    assert "NODO [Start_L]" in parsed_output
    assert "Eseguito da (Corsia/Ruolo): Generale / Non assegnata" in parsed_output


# 3. fault tolerance and resilience tests
def test_malformed_xml_raises_bpmn_parser_error():
    """Verify that malformed or corrupted XML content is caught without crashing."""
    corrupted_xml = "<definitions><process id='1'><task name='unclosed'></definitions>"
    with pytest.raises(BPMNParserError) as exc_info:
        parse_bpmn_to_text(corrupted_xml, is_file=False)
    assert "Errore durante la lettura dell'XML" in str(exc_info.value)


def test_invalid_namespace_raises_bpmn_parser_error():
    """Verify that valid XML with non-BPMN 2.0 namespace is rejected."""
    svg_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
      <circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" />
    </svg>
    """
    with pytest.raises(BPMNParserError) as exc_info:
        parse_bpmn_to_text(svg_xml, is_file=False)
    assert "Namespace non valido" in str(exc_info.value)


def test_missing_process_tag_raises_bpmn_parser_error():
    """Verify that BPMN files without an executable <process> tag are rejected."""
    empty_bpmn = """<?xml version="1.0" encoding="UTF-8"?>
    <definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
                 targetNamespace="http://bpmn.io/schema/bpmn">
    </definitions>
    """
    with pytest.raises(BPMNParserError) as exc_info:
        parse_bpmn_to_text(empty_bpmn, is_file=False)
    assert "Nessun tag <bpmn:process>" in str(exc_info.value)


def test_nonexistent_file_path_raises_bpmn_parser_error():
    """Verify that passing an invalid file path raises BPMNParserError gracefully."""
    with pytest.raises(BPMNParserError) as exc_info:
        parse_bpmn_to_text(Path("data/non_existent_process_12345.bpmn"), is_file=True)
    assert "Errore durante la lettura dell'XML" in str(exc_info.value)
