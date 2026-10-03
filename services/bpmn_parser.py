"""BPMN 2.0 parser and topological linearizer.

Extracts the semantic logic of BPMN 2.0 processes, stripping graphical metadata
(BPMN-DI) to minimize token consumption and LLM attention overhead.
"""

from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple, Union
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

# Standard BPMN 2.0 namespaces
BPMN_NS: Dict[str, str] = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}
BPMN_NS_URI: str = "http://www.omg.org/spec/BPMN/20100524/MODEL"


class BPMNParserError(Exception):
    """Raised when BPMN reading, parsing, or validation fails."""
    pass


def extract_lane_mappings(process_elem: Element, ns: Dict[str, str] = BPMN_NS) -> Dict[str, str]:
    """Map node IDs to their assigned Lane names (organizational roles)."""
    node_to_lane: Dict[str, str] = {}
    lanes = process_elem.findall(".//bpmn:lane", ns)
    for lane in lanes:
        lane_name = lane.get("name", "Senza Nome").strip()
        for node_ref in lane.findall(".//bpmn:flowNodeRef", ns):
            if node_ref.text:
                node_to_lane[node_ref.text.strip()] = lane_name
    return node_to_lane


def extract_nodes(process_elem: Element, node_to_lane: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """Extract operational nodes (Tasks, Events, Gateways) ignoring graphical DI tags."""
    nodes: Dict[str, Dict[str, str]] = {}
    for child in process_elem:
        tag_lower = child.tag.lower()
        if "task" in tag_lower or "event" in tag_lower or "gateway" in tag_lower:
            node_id = child.get("id")
            if not node_id:
                continue
            node_name = child.get("name", "").strip()
            node_type = child.tag.split("}")[-1]

            nodes[node_id] = {
                "id": node_id,
                "name": node_name if node_name else f"[{node_type} senza nome]",
                "type": node_type,
                "lane": node_to_lane.get(node_id, "Generale / Non assegnata"),
            }
    return nodes


def extract_connections_and_adjacency(process_elem: Element, nodes: Dict[str, Dict[str, str]], ns: Dict[str, str] = BPMN_NS,) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Build sequence flow descriptions and O(1) adjacency lookup in O(F) time."""
    flows = process_elem.findall(".//bpmn:sequenceFlow", ns)
    node_connections: Dict[str, List[str]] = {node_id: [] for node_id in nodes}
    adj: Dict[str, List[str]] = {node_id: [] for node_id in nodes}

    for flow in flows:
        source_id = flow.get("sourceRef")
        target_id = flow.get("targetRef")
        flow_name = flow.get("name", "").strip()

        if source_id in nodes and target_id in nodes:
            adj[source_id].append(target_id)
            target_name = nodes[target_id]["name"]
            connection_desc = f"-> {target_name} [ID: {target_id}] ({nodes[target_id]['type']})"
            if flow_name:
                connection_desc = f"-[{flow_name}]" + connection_desc
            node_connections[source_id].append(connection_desc)

    return node_connections, adj


def linearize_bpmn_bfs(nodes: Dict[str, Dict[str, str]], adj: Dict[str, List[str]],start_nodes: Optional[List[str]] = None,) -> List[str]:
    """Linearize nodes in causal topological order using BFS in O(N + F) time."""
    if start_nodes is None:
        start_nodes = [n_id for n_id, data in nodes.items() if data["type"] == "startEvent"]

    # Fallback to zero in-degree nodes if no explicit startEvent exists
    if not start_nodes and nodes:
        in_degree: Dict[str, int] = {n: 0 for n in nodes}
        for targets in adj.values():
            for t in targets:
                in_degree[t] = in_degree.get(t, 0) + 1
        zero_in = [n for n, deg in in_degree.items() if deg == 0]
        start_nodes = zero_in if zero_in else [list(nodes.keys())[0]]

    ordered_node_ids: List[str] = []
    visited: Set[str] = set()
    queue: Deque[str] = deque()

    # Enqueue valid start nodes (mark visited on enqueue to avoid duplicates)
    for sid in start_nodes:
        if sid in nodes and sid not in visited:
            visited.add(sid)
            queue.append(sid)

    # BFS traversal
    while queue:
        current_id = queue.popleft()
        ordered_node_ids.append(current_id)

        for target_id in adj.get(current_id, []):
            if target_id in nodes and target_id not in visited:
                visited.add(target_id)
                queue.append(target_id)

    # Handle disconnected/orphan nodes deterministically
    for node_id in sorted(nodes.keys()):
        if node_id not in visited:
            visited.add(node_id)
            ordered_node_ids.append(node_id)

    return ordered_node_ids


def format_topology(
    nodes: Dict[str, Dict[str, str]],
    node_connections: Dict[str, List[str]],
    ordered_node_ids: List[str],
) -> str:
    """Format the ordered process topology into a structured textual representation for LLM."""
    output_lines: List[str] = ["### DESCRIZIONE TOPOLOGICA DEL PROCESSO BPMN ###\n"]

    for node_id in ordered_node_ids:
        if node_id not in nodes:
            continue
        data = nodes[node_id]
        line = (
            f"- NODO [{data['id']}]: '{data['name']}'\n"
            f"  Tipo: {data['type']}\n"
            f"  Eseguito da (Corsia/Ruolo): {data['lane']}\n"
        )

        connections = node_connections.get(node_id, [])
        if connections:
            line += "  Connesso a: " + ", ".join(connections) + "\n"
        else:
            line += "  Connesso a: [Fine Flusso]\n"

        output_lines.append(line)

    return "\n".join(output_lines)


def parse_bpmn_to_text(file_path_or_content: Union[str, Path], is_file: bool = True) -> str:
    """Main function: parse and linearize a BPMN 2.0 XML diagram into causal text."""
    try:
        if is_file:
            root = ET.parse(str(file_path_or_content)).getroot()
        else:
            root = ET.fromstring(str(file_path_or_content))
    except (ET.ParseError, OSError, UnicodeDecodeError) as e:
        raise BPMNParserError(f"Errore durante la lettura dell'XML: {e}") from e
    except Exception as e:
        raise BPMNParserError(f"Errore imprevisto nel parsing XML: {e}") from e

    # Strict namespace validation on root element
    if not root.tag.startswith(f"{{{BPMN_NS_URI}}}"):
        raise BPMNParserError(
            f"Namespace non valido: il documento radice '{root.tag}' non appartiene allo standard BPMN 2.0 ({BPMN_NS_URI})."
        )

    process = root.find(".//bpmn:process", BPMN_NS)
    if process is None:
        raise BPMNParserError("Nessun tag <bpmn:process> (logica di processo) trovato nel file.")

    # 1. Extract lane mappings
    node_to_lane = extract_lane_mappings(process, BPMN_NS)

    # 2. Extract operational nodes
    nodes = extract_nodes(process, node_to_lane)

    # 3. Build sequence connections and adjacency list in O(F)
    node_connections, adj = extract_connections_and_adjacency(process, nodes, BPMN_NS)

    # 4. Linearize nodes via BFS in O(N + F)
    ordered_node_ids = linearize_bpmn_bfs(nodes, adj)

    # 5. Format into final textual topology
    return format_topology(nodes, node_connections, ordered_node_ids)
