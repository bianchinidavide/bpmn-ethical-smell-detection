from pathlib import Path
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

# setup jinja2 environment with autoescape for xss protection
template_dir = Path(__file__).resolve().parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True
)
template = env.get_template("ethical_card.html")

def render_card(violation: Any, kb_dict: dict[str, Any], node_name: Optional[str] = None) -> str:
    """Build HTML markup for an ethical violation card via Jinja2.
    Returns safe HTML string for Streamlit rendering.
    """
    smell_info = kb_dict.get(violation.codice_smell, {})
    
    name = smell_info.get("smell_name", f"Ethical Smell: {violation.codice_smell}")
    macro = smell_info.get("macro_principle", "Principio Non Specificato")
    rationale = smell_info.get("ethical_rationale", "Nessuna descrizione teorica disponibile.")
    
    rec_pattern = smell_info.get("recommendation_pattern", {})
    action = rec_pattern.get("action", "Nessuna azione correttiva suggerita.")
    bpmn_correction = rec_pattern.get("bpmn_correction", "").strip()
    if bpmn_correction:
        action = f"{action} {bpmn_correction}"
    
    sources = smell_info.get("sources", [])
    
    html_card = template.render(
        violation=violation,
        violazione=violation,
        node_name=node_name,
        name=name,
        macro=macro,
        rationale=rationale,
        action=action,
        sources=sources
    )
    
    return html_card.replace("\n", " ").replace("\r", "")