from __future__ import annotations
import asyncio
import os
import sys
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pipeline.graph import build_graph

st.set_page_config(
    page_title="ScholarStream AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; }

    /* Card style for agent outputs */
    .agent-card {
        background: #1a1d27;
        border: 1px solid #2e3347;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
    }
    .agent-card h3 {
        margin-top: 0;
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #7c8db5;
    }

    /* Status badges */
    .badge-waiting  { color: #7c8db5; font-size: 0.8rem; }
    .badge-running  { color: #f0a500; font-size: 0.8rem; }
    .badge-done     { color: #22c55e; font-size: 0.8rem; }

    /* Hero */
    .hero {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    .hero h1 { font-size: 2.4rem; font-weight: 800; color: #e2e8f0; }
    .hero p  { color: #7c8db5; font-size: 1rem; margin-top: -0.5rem; }

    /* Pipeline tracker */
    .pipeline-step {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 4px;
    }
    .step-idle    { background: #1e2235; color: #4a5568; border: 1px solid #2e3347; }
    .step-active  { background: #1a3a5c; color: #60aeff; border: 1px solid #2563eb; }
    .step-done    { background: #14532d; color: #4ade80; border: 1px solid #16a34a; }

    /* Download button */
    .stDownloadButton button {
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    /* Run button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        border: none;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1rem;
        padding: 0.6rem 2rem;
        color: white;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #13151f;
        border-right: 1px solid #2e3347;
    }

    /* Text area */
    .stTextArea textarea {
        background: #1a1d27;
        border: 1px solid #2e3347;
        border-radius: 8px;
        color: #e2e8f0;
        font-size: 0.95rem;
    }

    /* Divider */
    hr { border-color: #2e3347; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>📚 ScholarStream AI</h1>
    <p>Agentic Research & Literature Review Engine &nbsp;·&nbsp; LangChain + LangGraph + Groq</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input(
        "Groq API Key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Free key at console.groq.com — no credit card needed",
        placeholder="gsk_...",
    )

    st.divider()
    st.markdown("### 🗺️ Pipeline")
    for step in [
        ("🧠", "Planner",   "Decomposes query into task graph"),
        ("📡", "Retriever", "Fetches real papers from Semantic Scholar"),
        ("🔬", "Analyzer",  "Extracts architectural insights"),
        ("✍️", "Writer",    "Drafts publication-ready report"),
    ]:
        st.markdown(f"{step[0]} **{step[1]}** — {step[2]}")

    st.divider()
    st.markdown("### ⚡ Stack")
    st.code("LangGraph · LangChain\nChatGroq · Semantic Scholar\nStreamlit · asyncio", language="text")

DEFAULT = (
    "Analyze the intersection of contrastive learning and graph neural networks "
    "for customer churn prediction. Find relevant paper concepts, extract architectural "
    "constraints, outline a novel architecture, and write an abstract."
)

col_input, col_btn = st.columns([5, 1])
with col_input:
    prompt = st.text_area(
        "🔍 Research Query",
        value=DEFAULT,
        height=90,
        label_visibility="collapsed",
        placeholder="Enter your research question here...",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🚀 Run", type="primary", use_container_width=True)

st.divider()

status_placeholder = st.empty()

def render_status(states: dict):
    labels = {"planner": "🧠 Planner", "retriever": "📡 Retriever",
              "analyzer": "🔬 Analyzer", "writer": "✍️ Writer"}
    html = '<div style="text-align:center; margin-bottom:1rem;">'
    for key, label in labels.items():
        s = states.get(key, "idle")
        css = {"idle": "step-idle", "active": "step-active", "done": "step-done"}[s]
        html += f'<span class="pipeline-step {css}">{label}</span>'
    html += "</div>"
    status_placeholder.markdown(html, unsafe_allow_html=True)

# Initial render
render_status({})

col1, col2 = st.columns(2)

with col1:
    retriever_header = st.empty()
    retriever_body   = st.empty()
    retriever_header.markdown('<div class="agent-card"><h3>📡 Retriever — Papers Found</h3></div>', unsafe_allow_html=True)

with col2:
    analyzer_header = st.empty()
    analyzer_body   = st.empty()
    analyzer_header.markdown('<div class="agent-card"><h3>🔬 Analyzer — Insights</h3></div>', unsafe_allow_html=True)

writer_header = st.empty()
writer_body   = st.empty()
writer_header.markdown('<div class="agent-card"><h3>✍️ Writer — Final Report</h3></div>', unsafe_allow_html=True)

download_slot = st.empty()

if run_btn:
    if not api_key:
        st.error("⚠️ Add your Groq API key in the sidebar.")
        st.stop()
    if not prompt.strip():
        st.error("⚠️ Enter a research query.")
        st.stop()

    report_state = {"retriever": "", "analyzer": "", "writer": ""}
    node_status  = {"planner": "active", "retriever": "idle", "analyzer": "idle", "writer": "idle"}
    render_status(node_status)

    async def stream_graph():
        graph = build_graph(api_key=api_key)
        initial_state = {
            "user_prompt": prompt, "tasks": [],
            "retriever_output": "", "analyzer_output": "",
            "writer_output": "", "errors": [], "stream_log": [],
        }
        async for event in graph.astream(initial_state):
            node_name   = list(event.keys())[0]
            node_output = event[node_name]

            if node_name == "planner":
                node_status["planner"] = "done"
                node_status["retriever"] = "active"
                render_status(node_status)

            elif node_name == "retriever":
                node_status["retriever"] = "done"
                node_status["analyzer"]  = "active"
                render_status(node_status)
                report_state["retriever"] = node_output.get("retriever_output", "")
                retriever_header.markdown('<div class="agent-card"><h3>📡 Retriever — Papers Found</h3></div>', unsafe_allow_html=True)
                retriever_body.markdown(
                    f'<div style="background:#1a1d27;border:1px solid #2e3347;border-radius:8px;padding:16px;">{report_state["retriever"]}</div>',
                    unsafe_allow_html=True
                )

            elif node_name == "analyzer":
                node_status["analyzer"] = "done"
                node_status["writer"]   = "active"
                render_status(node_status)
                report_state["analyzer"] = node_output.get("analyzer_output", "")
                analyzer_header.markdown('<div class="agent-card"><h3>🔬 Analyzer — Insights</h3></div>', unsafe_allow_html=True)
                analyzer_body.markdown(
                    f'<div style="background:#1a1d27;border:1px solid #2e3347;border-radius:8px;padding:16px;">{report_state["analyzer"]}</div>',
                    unsafe_allow_html=True
                )

            elif node_name == "writer":
                node_status["writer"] = "done"
                render_status(node_status)
                report_state["writer"] = node_output.get("writer_output", "")
                writer_header.markdown('<div class="agent-card"><h3>✍️ Writer — Final Report</h3></div>', unsafe_allow_html=True)
                writer_body.markdown(
                    f'<div style="background:#1a1d27;border:1px solid #2e3347;border-radius:8px;padding:16px;">{report_state["writer"]}</div>',
                    unsafe_allow_html=True
                )

    try:
        asyncio.run(stream_graph())
        st.success("✅ Pipeline complete!")

        if report_state["writer"]:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_report = (
                f"# ScholarStream AI Report\n"
                f"**Generated:** {datetime.now().strftime('%B %d, %Y %H:%M')}\n\n"
                f"**Query:** {prompt}\n\n"
                f"## Retrieved Papers\n{report_state['retriever']}\n\n"
                f"## Analysis\n{report_state['analyzer']}\n\n"
                f"## Final Report\n{report_state['writer']}"
            )
            download_slot.download_button(
                label="⬇️ Download Full Report (.md)",
                data=full_report,
                file_name=f"scholarstream_report_{ts}.md",
                mime="text/markdown",
                use_container_width=True,
            )
    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")