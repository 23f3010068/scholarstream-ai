from __future__ import annotations
import functools
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from ..agents.state import ResearchState
from ..agents.nodes import planner_node, retriever_node, analyzer_node, writer_node


def build_graph(api_key: str) -> StateGraph:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=api_key,
        streaming=True,
    )
    planner  = functools.partial(planner_node,  llm=llm)
    retriever = functools.partial(retriever_node, llm=llm)
    analyzer  = functools.partial(analyzer_node,  llm=llm)
    writer    = functools.partial(writer_node,    llm=llm)

    graph = StateGraph(ResearchState)

    graph.add_node("planner",   planner)
    graph.add_node("retriever", retriever)
    graph.add_node("analyzer",  analyzer)
    graph.add_node("writer",    writer)

    graph.set_entry_point("planner")
    graph.add_edge("planner",   "retriever")
    graph.add_edge("retriever", "analyzer")
    graph.add_edge("analyzer",  "writer")
    graph.add_edge("writer",    END)

    return graph.compile()
