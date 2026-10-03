import base64
from typing import Optional
import streamlit as st

from bpmn_parser import parse_bpmn_to_text, BPMNParserError
from services.auditor import run_auditor

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg"}
MAX_WORDS_LIMIT = 200

def render_input_view() -> None:
    """Render the input acquisition view for BPMN ethical audit."""
    
    # Header section
    st.markdown(
        """
    <div class="hero-header">
        <h1>Ethical smells detection</h1>
        <p>Questo strumento automatizzato sfrutta il modello Claude Opus per eseguire la revisione etica di processi aziendali modellati in BPMN, confrontandoli con una Knowledge Base di riferimento contenente le regole e i pattern di rischio etico codificati. Carica il file di processo e fornisci il contesto operativo per individuare potenziali criticità, come discriminazioni, bias algoritmici o asimmetrie informative.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Body section
    col1, col2 = st.columns([1, 1.2], gap="large")

    with col1:
        st.markdown(
            """
        <div class="compilation-guide" style="border-right: 1px solid #cbd5e1; padding-right: 2.5rem; height: 100%; min-height: 400px; margin-right: -1rem;">
            <h3 style="font-weight: 400; margin-bottom: 1rem; margin-top: 0;">Guida alla compilazione</h3>
            <p style="font-size: 1.05rem; line-height: 1.7; font-weight: 300;">
            Per consentire un'analisi accurata è obbligatorio fare l'upload del file (.bpmn) del processo e inserire una descrizione indicando:
            </p>
            <ul style="font-size: 1.05rem; line-height: 1.7; font-weight: 300;">
                <li style="font-size: 1.05rem; line-height: 1.7; font-weight: 300; margin-bottom: 0.5rem;"><strong>Obiettivo del processo</strong>: qual è lo scopo o il fine ultimo del flusso (es. selezione del personale, erogazione di un prestito).</li>
                <li style="font-size: 1.05rem; line-height: 1.7; font-weight: 300; margin-bottom: 0.5rem;"><strong>Soggetti coinvolti</strong>: chi opera nel processo e quali utenti o categorie ne subiscono gli effetti (es. consumatori, candidati, dipendenti).</li>
                <li style="font-size: 1.05rem; line-height: 1.7; font-weight: 300;"><strong>Ambito operativo</strong>: cosa fa il processo a livello pratico e in quale contesto aziendale si colloca (es. piattaforma e-commerce, servizi bancari, fitness club).</li>
            </ul>
            <p style="font-size: 0.95rem; line-height: 1.6; font-weight: 400; color: #475569; margin-top: 1.5rem; border-top: 1px dashed #cbd5e1; padding-top: 1rem;">
            Inserisci esclusivamente la descrizione oggettiva del processo. Non aggiungere istruzioni, comandi o richieste dirette per il modello.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.subheader("1. File di processo")

        col_up1, col_up2 = st.columns([1, 1], gap="small")
        with col_up1:
            bpmn_file = st.file_uploader("Modello (.bpmn) *", type=["bpmn", "xml"])
        with col_up2:
            img_file = st.file_uploader(
                "Immagine del diagramma (opzionale)", type=["png", "jpg", "jpeg"]
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("2. Descrizione del processo")

        # Retrieve saved prompt if returning from results view
        previous_prompt = st.session_state.get("saved_prompt", "")

        user_prompt = st.text_area(
            f"Descrizione del contesto operativo (max {MAX_WORDS_LIMIT} parole) *",
            value=previous_prompt,
            height=150,
            placeholder="Es. Il processo modella l'iscrizione (abbonamento) a una catena di palestre fisiche, gestendo la raccolta anagrafica, il pagamento ricorrente e la procedura di recesso per i clienti [...]",
            help="Fornisci una descrizione chiara e sintetica degli obiettivi e degli attori coinvolti nel flusso.",
        )

        word_count = len(user_prompt.split()) if user_prompt else 0
        if word_count > MAX_WORDS_LIMIT:
            st.error(
                f"Limite superato: {word_count}/{MAX_WORDS_LIMIT} parole. Sintetizza il testo per procedere."
            )
        elif word_count > 0:
            st.caption(f"Parole utilizzate: {word_count}/{MAX_WORDS_LIMIT}")

        st.markdown("<br>", unsafe_allow_html=True)

        submit_clicked: bool = False        
        can_analyze = (bpmn_file is not None) and (0 < word_count <= MAX_WORDS_LIMIT)

        col_spacer, col_btn = st.columns([3, 2])
        with col_btn:
            submit_clicked = st.button(
                "Avvia revisione etica",
                type="primary",
                disabled=not can_analyze,
                use_container_width=True,
            )

    # Analysis execution
    if submit_clicked:
        # Preserve prompt in session state for back-navigation
        st.session_state["saved_prompt"] = user_prompt

        # Validate and decode BPMN file to UTF-8
        try:
            bpmn_string = bpmn_file.getvalue().decode("utf-8")
        except UnicodeDecodeError:
            st.error(
                "Il file BPMN caricato non ha una codifica UTF-8 valida. Si prega di verificare o riesportare il file."
            )
            return

        # Validate and encode optional image
        image_data: Optional[str] = None
        image_media_type: Optional[str] = None
        if img_file is not None:
            if img_file.type not in ALLOWED_IMAGE_TYPES:
                st.error(
                    f"Formato immagine non supportato ({img_file.type}). Sono supportati esclusivamente file PNG e JPEG."
                )
                return
            image_data = base64.b64encode(img_file.getvalue()).decode("utf-8")
            image_media_type = img_file.type

        # Fullscreen loading overlay protected by finally block
        overlay = st.empty()
        report = None
        error = None
        debug_info = None
        parsed_text = ""

        try:
            overlay.markdown(
                """
            <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.7); z-index: 99999; display: flex; justify-content: center; align-items: center; flex-direction: column;">
                <div style="border: 6px solid #334155; border-top: 6px solid #4da6ff; border-radius: 50%; width: 70px; height: 70px; animation: spin 1s linear infinite;"></div>
                <p style="color: white; margin-top: 20px; margin-bottom: 0px; font-family: 'Poppins', sans-serif; font-size: 1.3rem; font-weight: 300; letter-spacing: 1px;">Analisi etica in corso...</p>
                <p style="color: #cbd5e1; margin-top: 8px; font-family: 'Poppins', sans-serif; font-size: 0.95rem; font-weight: 300;">L'operazione può richiedere qualche minuto.</p>
                <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
            </div>
            """,
                unsafe_allow_html=True,
            )

            # Execute parser to extract linear process topology
            parsed_text = parse_bpmn_to_text(bpmn_string, is_file=False)

            # Execute semantic audit via auditor module
            report, error, debug_info = run_auditor(
                parsed_text, user_prompt, image_data, image_media_type
            )

        except BPMNParserError as err: #error from parser
            st.error(f"Errore durante l'elaborazione del diagramma BPMN: {err}")
            return
        except Exception as e: # Extra to control error 
            st.error(f"Si è verificato un errore imprevisto durante l'analisi: {e}")
            return
        finally:
            # Guaranteed removal of overlay in any scenario (success or exception)
            overlay.empty()

        # Handle analysis outcome, possible error from auditor
        if error:
            st.error(error)
        else:
            st.session_state["report"] = report
            st.session_state["bpmn_content"] = bpmn_string
            st.session_state["testo_parsato"] = parsed_text
            st.session_state["saved_prompt"] = user_prompt
            st.session_state["current_view"] = "results"
            st.rerun()
