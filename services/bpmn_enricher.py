import xml.etree.ElementTree as ET
import defusedxml.ElementTree as SafeET
from typing import Any

# standard bpmn and coloring namespaces
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
BIOC_NS = "http://bpmn.io/schema/bpmn/biocolor/1.0"
COLOR_NS = "http://www.omg.org/spec/BPMN/non-normative/color/1.0"

def enrich_bpmn_xml(original_xml: str, violations: list[Any], kb_dict: dict[str, Any]) -> str:
    """Enrich BPMN 2.0 XML with:
    1. 'bioc' and 'color' standard attributes to highlight violated nodes in red (#d93025).
    2. <bpmn:documentation> tags containing ethical smell diagnosis, rationale, and mitigations.
    """
    if not violations:
        return original_xml

    # register standard namespaces to preserve exact xml prefixes
    ET.register_namespace('bpmn', BPMN_NS)
    ET.register_namespace('bpmndi', BPMNDI_NS)
    ET.register_namespace('dc', DC_NS)
    ET.register_namespace('di', DI_NS)
    ET.register_namespace('bioc', BIOC_NS)
    ET.register_namespace('color', COLOR_NS)

    # safe parsing with defusedxml to guard against xml vulnerabilities
    try:
        root = SafeET.fromstring(original_xml)
    except Exception:
        try:
            # fallback for xml strings with character encoding declaration mismatches
            root = SafeET.fromstring(original_xml.encode('utf-8'))
        except Exception:
            return original_xml

    # violation mapping indexed by node id (supports pydantic objects and dicts)
    v_map = {}
    for v in violations:
        node_id = getattr(v, 'id_nodo', None) or (v.get('id_nodo') if isinstance(v, dict) else None)
        if node_id:
            v_map[node_id] = v

    ns = {
        'bpmn': BPMN_NS,
        'bpmndi': BPMNDI_NS
    }

    # 1. inject ethical documentation into semantic process nodes
    for process in root.findall('.//bpmn:process', ns):
        for child in process:
            node_id = child.get('id')
            if node_id in v_map:
                v = v_map[node_id]
                smell_code = getattr(v, 'codice_smell', None) or (v.get('codice_smell') if isinstance(v, dict) else '')
                explanation = getattr(v, 'spiegazione', None) or (v.get('spiegazione') if isinstance(v, dict) else '')
                
                smell = kb_dict.get(smell_code, {})
                smell_name = smell.get('smell_name', smell_code)
                macro = smell.get('macro_principle', 'Principio Etico')
                rationale = smell.get('ethical_rationale', 'Nessun razionale disponibile.')
                rec = smell.get('recommendation_pattern', {})
                action = rec.get('action', 'Nessuna azione correttiva definita.')
                bpmn_correction = rec.get('bpmn_correction', '').strip()
                if bpmn_correction:
                    action = f"{action} {bpmn_correction}"
                sources = smell.get('sources', [])
                sources_str = ", ".join(sources) if sources else "Non specificate"

                doc_text = (
                    f"=== REVISIONE ETICA DEL PROCESSO ===\n"
                    f"Codice smell: {smell_code} — {smell_name}\n"
                    f"Macro-principio etico violato: {macro}\n\n"
                    f"Diagnosi dell'LLM:\n{explanation}\n\n"
                    f"Razionale etico:\n{rationale}\n\n"
                    f"Suggerimento per la mitigazione della criticità:\n{action}\n\n"
                    f"Fonti normative e standard di riferimento:\n{sources_str}\n"
                    f"====================================="
                )

                # check if <documentation> element already exists
                doc_elem = child.find('bpmn:documentation', ns)
                if doc_elem is None:
                    # insert at index 0 conforming to bpmn 2.0 xsd element ordering (tBaseElement)
                    doc_elem = ET.Element(f'{{{BPMN_NS}}}documentation')
                    child.insert(0, doc_elem)
                    doc_elem.text = doc_text
                else:
                    doc_elem.text = (doc_elem.text or '') + "\n\n" + doc_text

    # 2. inject chromatic styles using clark notation to guarantee namespace declaration
    for shape in root.findall('.//bpmndi:BPMNShape', ns):
        bpmn_el = shape.get('bpmnElement')
        if bpmn_el in v_map:
            # alert red stroke (#d93025) and light red fill (#fce8e6)
            shape.set(f'{{{BIOC_NS}}}stroke', '#d93025')
            shape.set(f'{{{BIOC_NS}}}fill', '#fce8e6')
            shape.set(f'{{{COLOR_NS}}}border-color', '#d93025')
            shape.set(f'{{{COLOR_NS}}}background-color', '#fce8e6')

    # serialize to utf-8 xml string with xml declaration header
    enriched_xml = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
    return enriched_xml
