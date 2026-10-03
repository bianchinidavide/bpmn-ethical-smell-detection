import re
import time
from typing import Optional
import streamlit as st
import streamlit.components.v1 as components

from services.knowledge_base import load_kb
from services.bpmn_enricher import enrich_bpmn_xml
from components.ethical_card import render_card
from components.bpmn_viewer import render_bpmn_html

def render_results_view():
    # defensive state check: if page is reloaded with empty state, redirect to input view
    if "report" not in st.session_state or "bpmn_content" not in st.session_state:
        st.session_state["current_view"] = "input"
        st.rerun()

    report = st.session_state["report"]
    bpmn_xml = st.session_state["bpmn_content"]
    parsed_text = st.session_state.get("testo_parsato", "")
    user_prompt = st.session_state.get("saved_prompt", "")
    kb_dict = load_kb()
    if not kb_dict:
        st.error("Knowledge base non disponibile o corrotta. Verifica il file data/knowledge_base.json.")
        st.stop()

    # navigation and download action buttons
    st.markdown("<br>", unsafe_allow_html=True)
    col_back, col_download, col_spacer, col_new = st.columns([1.2, 1.4, 2.8, 1.2])
    with col_back:
        if st.button("← Torna Indietro", use_container_width=True):
            st.session_state["current_view"] = "input"
            st.rerun()
    with col_download:
        if st.button("↓ Download analisi", use_container_width=True):
            components.html(
                f"""
            <script>
                // Trigger id: {time.time()}
                if (window.parent && window.parent.startAnalysisDownload) {{
                    window.parent.startAnalysisDownload();
                }} else if (window.startAnalysisDownload) {{
                    window.startAnalysisDownload();
                }} else {{
                    alert("Diagramma non ancora pronto. Attendi qualche istante e riprova.");
                }}
            </script>
            """,
                height=0,
            )
    with col_new:
        if st.button("Nuova Analisi →", use_container_width=True):
            st.session_state["saved_prompt"] = ""
            st.session_state["current_view"] = "input"
            st.rerun()

    # header
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='font-weight: 400; color: #0f172a; margin-bottom: 5px;'>Report della revisione etica del processo</h2>",
        unsafe_allow_html=True,
    )

    def get_node_name(node_id: str, text: str) -> Optional[str]:
        # extract node display name handling quotes and excluding generic placeholders
        match = re.search(rf"- NODO \[{re.escape(node_id)}\]:\s*'(.*)'", text)
        if match:
            extracted_name = match.group(1).strip()
            if extracted_name and not (extracted_name.startswith("[") and extracted_name.endswith("]")):
                return extracted_name
        return None

    # build tooltips, cards, and structured violation data
    tooltip_data = {}
    rendered_cards = []
    violations_data = []

    for violation in report.violazioni:
        smell_info = kb_dict.get(violation.codice_smell, {})
        smell_name = smell_info.get("smell_name", violation.codice_smell)
        macro_principle = smell_info.get("macro_principle", "Principio Non Specificato")
        ethical_rationale = smell_info.get("ethical_rationale", "Nessuna descrizione teorica disponibile.")
        recommendation_pattern = smell_info.get("recommendation_pattern", {})
        action = recommendation_pattern.get("action", "Nessuna azione correttiva suggerita.")
        bpmn_correction = recommendation_pattern.get("bpmn_correction", "").strip()
        if bpmn_correction:
            action = f"{action} {bpmn_correction}"
        sources = smell_info.get("sources", [])

        tooltip_data[violation.id_nodo] = {"codice": violation.codice_smell, "nome": smell_name}
        node_display_name = get_node_name(violation.id_nodo, parsed_text)
        card_html = render_card(violation, kb_dict, node_name=node_display_name)
        rendered_cards.append((violation.id_nodo, card_html))

        violations_data.append({
            "node_id": violation.id_nodo,
            "node_name": node_display_name if node_display_name else violation.id_nodo,
            "code": violation.codice_smell,
            "name": smell_name,
            "macro": macro_principle,
            "diagnosis": violation.spiegazione,
            "rationale": ethical_rationale,
            "action": action,
            "sources": sources,
        })

    # structured payload for the formal pdf generation engine
    report_data = {
        "context": user_prompt if user_prompt else "Nessun contesto specificato.",
        "num_violations": len(report.violazioni),
        "violations": violations_data,
    }

    # semantic and chromatic enrichment of bpmn xml
    enriched_bpmn = enrich_bpmn_xml(bpmn_xml, report.violazioni, kb_dict)

    # summary message with singular/plural grammatical handling
    num_violations = len(report.violazioni)
    if num_violations == 0:
        st.markdown(
            "<p style='font-size: 1.15rem; color: #0f172a; font-weight: 300;'>Analisi completata. Il processo risulta <strong style='color: #059669;'>conforme</strong> ai principi etici analizzati.</p>",
            unsafe_allow_html=True,
        )
    else:
        smell_label = "ethical smell" if num_violations == 1 else "ethical smells"
        verb_label = "Individuato" if num_violations == 1 else "Individuati"
        st.markdown(
            f"<p style='font-size: 1.15rem; color: #0f172a; font-weight: 300;'>Analisi completata. {verb_label} <strong style='color: #d93025;'>{num_violations} {smell_label}</strong> all'interno del processo.</p>",
            unsafe_allow_html=True,
        )

    # interactive bpmn canvas
    st.markdown("<br>", unsafe_allow_html=True)
    render_bpmn_html(
        bpmn_xml=bpmn_xml,
        tooltip_data=tooltip_data,
        enriched_bpmn=enriched_bpmn,
        report_data=report_data,
    )

    # violation detail cards anchored by node id
    if report.violazioni:
        st.markdown(
            "<br><h3 style='font-weight: 400; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 20px;'>Dettaglio delle violazioni</h3>",
            unsafe_allow_html=True,
        )
        for node_id, card_html in rendered_cards:
            st.markdown(
                f'<div id="card-{node_id}" style="position: relative; top: -50px;"></div>{card_html}',
                unsafe_allow_html=True,
            )
