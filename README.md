# Ethical smells detection in Business Processes (BPMN)

An automated ethical auditing framework designed to detect ethical risks and anti-patterns (**ethical smells**) in BPMN 2.0 business process models using **Claude Opus** and a codified ethical Knowledge Base. Developed as part of a Master's Thesis in Computer Science and Engineering.

---

## Overview

Research prototype developed as part of a Master's Thesis to detect ethical risks (*ethical smells*) in BPMN 2.0 business processes. 

The pipeline works in three main steps:
1. **Topology Extraction**: Parses the BPMN 2.0 XML diagram, strips graphical overhead, and causally linearizes operational nodes via Breadth-First Search (BFS).
2. **LLM-Based Audit**: Evaluates the linearized process and its operational context against a codified ethical Knowledge Base using Claude Opus.
3. **Results & Export**: Highlights flagged nodes on an interactive BPMN canvas, enriches the BPMN XML with standard BPMN-in-Color attributes and documentation, and exports a comprehensive PDF audit report.

---

## Installation

### Prerequisites
- Python 3.10 or higher
- Git

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/ethical_smells_detection_BPMN.git
   cd ethical_smells_detection_BPMN
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration & API Keys

The application supports both live LLM auditing via Anthropic's Claude API and an offline mock evaluation mode.

### 1. Live analysis with Anthropic Claude Opus
To run live ethical audits with Claude Opus, provide your Anthropic API key using one of the following methods:

- **Option A (Recommended — `.env` file)**:
  Copy the provided example file:
  ```bash
  cp .env.example .env
  ```
  Open `.env` and set your key:
  ```env
  ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
  ```

- **Option B (Streamlit Secrets)**:
  Create `.streamlit/secrets.toml`:
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-api03-your-key-here"
  ```

### 2. Offline mock mode (Zero-Cost Evaluation)
If `ANTHROPIC_API_KEY` is not provided, left empty, or invalid:
- The application automatically switches to **Mock Mode**.
- **No external API calls are made and zero tokens are consumed.**
- The system loads benchmark response data (`data/mock_response.json`), allowing full evaluation of the frontend, BPMN enrichment, interactive canvas, and PDF export without an API key or internet access.

---

## Running the application

Launch the Streamlit web interface:
```bash
streamlit run app.py
```

The application will be available in your browser at `http://localhost:8501`.

---

## License

This project is released under the [MIT License](LICENSE).
