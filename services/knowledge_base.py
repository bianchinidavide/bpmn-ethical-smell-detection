import json
import logging
from pathlib import Path
from typing import Any
import streamlit as st

logger = logging.getLogger(__name__)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"

REQUIRED_FIELDS = {"id", "smell_name", "macro_principle"}


def _load_kb_from_disk(path: Path) -> dict[str, dict[str, Any]]:
    """Load knowledge base from disk without streamlit dependencies."""
    if not path.is_file():
        logger.error("Knowledge base not found at: %s", path)
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Malformed JSON in %s: %s", path, e)
        return {}
    except OSError as e:
        logger.error("I/O error reading %s: %s", path, e)
        return {}

    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, list):
        logger.error("KB must be a list or dict, found %s", type(raw).__name__)
        return {}

    kb: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            logger.warning("Item #%d is not a dict: %r", i, item)
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            logger.warning("Item #%d missing valid id: %r", i, item)
            continue
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            logger.warning("Item %s missing required fields: %s", item_id, sorted(missing))
        kb[item_id] = item

    logger.info("Knowledge base successfully loaded: %d items from %s", len(kb), path)
    return kb


@st.cache_data(show_spinner=False)
def load_kb() -> dict[str, dict[str, Any]]:
    """Load knowledge base with streamlit caching for optimal ui performance."""
    return _load_kb_from_disk(KB_PATH)
