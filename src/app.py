from __future__ import annotations
import asyncio
import os
import sys
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pipeline.graph import build_graph

st.set_page_config(
    page_title="ScholarStream AI",
    page_icon="📚",
    layout="wide",
)

st.title("📚 ScholarStream AI")
st.caption("Agentic Research & Literature Review Engine — LangChain + LangGraph")

with st.sidebar:
    st.header("⚙️ Config")
    api_key = st.text_input(
        "Groq API Key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Get a free key at console.groq.com",
    )
    st.divider()
    st.markdown("**Pipeline:**")
    st.markdown("1. 🧠 Planner — decomposes query")
    st.markdown("2. 📡 Retriever — fetches papers")
    st.markdown("3. 🔬 Analyzer — extracts insights")
    st.markdown("4. ✍️ Writer — drafts report")

DEFAULT = (
    "Analyze the intersection of contrastive learning and graph neural networks "
    "for customer churn prediction. Find relevant paper concepts, extract architectural "
    "constraints, outline a novel architecture, and write an abstract."
)

prompt = st.text_area("🔍 Research Query", value=DEFAULT, height=100)

run_btn = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

if run_btn:
    if not api_key:
        st.error("Add your Groq API key in the sidebar first.")
        st.stop()
    if not prompt.strip():
        st.error("Enter a research query.")
        st.stop()

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    indicators = {
        "planner":   col1.empty(),
        "retriever": col2.empty(),
        "analyzer":  col3.empty(),
        "writer":    col4.empty(),
    }
    for name, slot in indicators.items():
        slot.info(f"⏳ {name.capitalize()}")

    st.subheader("📡 Retriever Output")
    retriever_box = st.empty()

    st.subheader("🔬 Analyzer Output")
    analyzer_box = st.empty()

    st.subheader("✍️ Final Report")
    writer_box = st.empty()

    report_state = {"retriever": "", "analyzer": "", "writer": ""}

    async def stream_graph():
        graph = build_graph(api_key=api_key)
        initial_state = {
            "user_prompt":      prompt,
            "tasks":            [],
            "retriever_output": "",
            "analyzer_output":  "",
            "writer_output":    "",
            "errors":           [],
            "stream_log":       [],
        }
        async for event in graph.astream(initial_state):
            node_name   = list(event.keys())[0]
            node_output = event[node_name]

            if node_name == "planner":
                indicators["planner"].success("✅ Planner")

            elif node_name == "retriever":
                indicators["retriever"].success("✅ Retriever")
                report_state["retriever"] = node_output.get("retriever_output", "")
                retriever_box.markdown(report_state["retriever"])

            elif node_name == "analyzer":
                indicators["analyzer"].success("✅ Analyzer")
                report_state["analyzer"] = node_output.get("analyzer_output", "")
                analyzer_box.markdown(report_state["analyzer"])

            elif node_name == "writer":
                indicators["writer"].success("✅ Writer")
                report_state["writer"] = node_output.get("writer_output", "")
                writer_box.markdown(report_state["writer"])

    try:
        asyncio.run(stream_graph())
        st.success("✅ Pipeline complete!")

        if report_state["writer"]:
            full_report = (
                f"# ScholarStream AI Report\n\n"
                f"**Query:** {prompt}\n\n"
                f"## Retrieved Papers\n{report_state['retriever']}\n\n"
                f"## Analysis\n{report_state['analyzer']}\n\n"
                f"## Final Report\n{report_state['writer']}"
            )
            st.download_button(
                label="⬇️ Download Report as Markdown",
                data=full_report,
                file_name="scholarstream_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")