from __future__ import annotations
from langchain_core.tools import tool


@tool
def fetch_papers(query: str) -> str:
    """Simulates fetching top 3 academic paper concepts for a research query."""
    return f"[Tool:fetch_papers] Received query: {query} — ready for LLM retrieval."


@tool
def extract_constraints(papers_text: str) -> str:
    """Extracts architectural constraints and research gaps from paper summaries."""
    return f"[Tool:extract_constraints] Received {len(papers_text)} chars — ready for LLM analysis."


@tool
def write_report(analysis_text: str) -> str:
    """Synthesizes analysis into a publication-ready academic report section."""
    return f"[Tool:write_report] Received {len(analysis_text)} chars — ready for LLM writing."
