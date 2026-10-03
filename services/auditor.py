import json
import os
import traceback
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
import streamlit as st # type: ignore
import anthropic
from pydantic import BaseModel, Field, ConfigDict

# Load environment variables from .env file (if present)
load_dotenv()

# Absolute paths to data assets
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KB_PATH = DATA_DIR / "knowledge_base.json"
MOCK_PATH = DATA_DIR / "mock_response.json"

# Reference Anthropic Claude model for the thesis
MODEL_NAME = "claude-opus-5"

# PYDANTIC schema for structured outputs ---
class Violazione(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_nodo: str = Field(description="L'ID univoco del nodo BPMN incriminato (es. Task_123, Gateway_456)")
    codice_smell: str = Field(description="Il codice dello smell etico violato, preso dalla Knowledge Base (es. ES-19)")
    spiegazione: str = Field(description="Spiegazione dettagliata del perché questo nodo viola l'etica, basata sul contesto e sulle regole.")

class ReportEtico(BaseModel):
    model_config = ConfigDict(extra="forbid")
    violazioni: list[Violazione] = Field(description="Lista dei nodi che violano gli ethical smells. Se non ci sono violazioni, lascia l'array vuoto.")

def filter_referential_integrity(
    report: ReportEtico,
    valid_node_ids: set[str],
    valid_smell_codes: set[str]
) -> ReportEtico:
    """Filter out violations with invalid or hallucinated node IDs or smell codes.
    
    Cross-checks the model findings against the real nodes in the BPMN process
    and the valid smell catalog from the Knowledge Base.
    """
    valid_violations = [
        v for v in report.violazioni
        if v.id_nodo in valid_node_ids and v.codice_smell in valid_smell_codes
    ]
    return ReportEtico(violazioni=valid_violations)

# api function
def run_auditor(parsed_text: str, user_context: str, image_base64: Optional[str] = None, image_media_type: Optional[str] = None, api_key: Optional[str] = None) -> tuple[Optional[ReportEtico], Optional[str], dict[str, Any]]:
    """Execute ethical audit using Anthropic Claude (claude-opus-5) native output_config.
    
    Returns:
        tuple: (report: ReportEtico, error: str, debug_info: dict)
    """
    # 1. Load Knowledge Base for the system prompt
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb_content = f.read()
    except Exception as e:
        return None, f"Errore nel caricamento della Knowledge Base ({KB_PATH}): {e}", {}

    system_prompt = f"""Sei un auditor etico specializzato in processi aziendali (BPMN). 
Il tuo obiettivo è analizzare il processo per individuare potenziali violazioni etiche (denominate ethical smells). 
Sei rigoroso, oggettivo e non allucini. 
Per individuare le violazioni usa esclusivamente le regole presenti in questa Knowledge Base ufficiale. 
Per ognuna, segui rigorosamente i "reasoning_steps" forniti e usa gli "examples" per capire i pattern delle violazioni: 
{kb_content}"""

    instruction_prompt = """Ora esegui l'audit etico sul processo appena fornito. Linee guida per l'analisi e l'output:
- Fai la tua analisi strutturale passo passo sfruttando il tuo ragionamento interno. Analizza prima il contesto dell'utente, guarda il processo nella sua interezza e poi scansiona ogni nodo per verificare se corrisponde ai pattern pericolosi della Knowledge Base.
- Valuta le eccezioni: Se un nodo solleva dubbi ma ricade nelle eccezioni etiche giustificate descritte nella Knowledge Base, scartalo e non segnalarlo come violazione.
- Restituisci come output unicamente l'array 'violazioni', associando ogni criticità reale al nodo esatto."""

    # Merge context with semantic XML delimiters (Anthropic recommended standard)
    full_text = f"""<descrizione_processo>
{user_context}
</descrizione_processo>

<processo_bpmn>
{parsed_text}
</processo_bpmn>

{instruction_prompt}"""
    
    message_content = []
    
    if image_base64 and image_media_type:
        message_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_media_type,
                "data": image_base64
            }
        })
        
    message_content.append({
        "type": "text",
        "text": full_text
    })

    schema_json = ReportEtico.model_json_schema()

    debug_info: dict[str, Any] = {
        "model": MODEL_NAME,
        "system_prompt": system_prompt,
        "user_message": message_content,
        "schema": schema_json,
        "raw_response": None
    }

    # 2. Retrieve API Key (explicit parameter -> environment -> Streamlit Secrets)
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass

    if api_key:
        api_key = api_key.strip()
           
    # Mock mode: active if key is missing or invalid (real keys start with sk-ant-)
    if not api_key or not api_key.startswith("sk-ant"):
        try:
            with open(MOCK_PATH, "r", encoding="utf-8") as f:
                mock_text = f.read()
            report = ReportEtico.model_validate_json(mock_text)
            debug_info["mock_mode"] = True
            debug_info["raw_response"] = {
                "info": "Mock mode",
                "simulated_report": report.model_dump()
            }
            return report, None, debug_info
        except Exception as e:
            return None, f"API Key mancante e fallimento lettura mock ({MOCK_PATH}): {e}", debug_info

    # 3. Anthropic API Call
    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=240.0)

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,
            system=system_prompt,
            messages=[
                {"role": "user", "content": message_content}
            ],
            output_config={
                "effort": "high",
                "format": {
                    "type": "json_schema",
                    "schema": schema_json
                }
            }
        )
        
        # 4. Result parsing
        stop_reason = getattr(response, "stop_reason", "unknown")
        
        # Claude Opus returns thinking blocks followed by the structured text block
        thinking_text = next((getattr(block, 'thinking', '') for block in response.content if getattr(block, 'type', '') == "thinking"), "")
        result_text = next((getattr(block, 'text', '') for block in response.content if getattr(block, 'type', '') == "text"), "")
        
        # Store full raw response for debug inspection
        debug_info["raw_response"] = {
            "stop_reason": stop_reason,
            "stop_details": str(getattr(response, "stop_details", None)),
            "content_blocks": [str(b) for b in response.content],
            "extracted_text": result_text,
            "thinking_text": thinking_text
        }
        
        if stop_reason == "max_tokens":
            return None, "L'analisi ha esaurito i token massimi consentiti (max_tokens). La risposta dell'AI è stata troncata.", debug_info
        
        if not result_text.strip():
            return None, f"L'API ha restituito una risposta vuota o bloccata. Motivo stop: {stop_reason}. Controlla il payload di debug.", debug_info
        
        try:
            report = ReportEtico.model_validate_json(result_text)
            return report, None, debug_info
        except Exception as e:
            return None, f"Errore nel parsing JSON di Pydantic: {str(e)}\n\nTesto ricevuto dall'AI:\n{result_text}", debug_info

    except Exception as e:
        debug_info["traceback"] = traceback.format_exc()
        return None, f"Errore durante l'analisi con l'API Anthropic: {str(e)}", debug_info
