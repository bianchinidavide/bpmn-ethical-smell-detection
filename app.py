from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

from views.input_view import render_input_view
from views.results_view import render_results_view

# Load (.env) - check .env.example for instructions
load_dotenv()

# UI Streamlit setup
st.set_page_config(
    page_title="BPMN Ethical Smell Detection",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS dynamic loading
css_path = Path(__file__).resolve().parent / "assets" / "style.css"
if css_path.is_file():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# SPA state management
if "current_view" not in st.session_state:
    st.session_state["current_view"] = "input"

if st.session_state["current_view"] == "input":
    render_input_view()
elif st.session_state["current_view"] == "results":
    render_results_view()
else:  # Defensive fallback
    st.session_state["current_view"] = "input"
    st.rerun()