from __future__ import annotations
import json
import logging
import random
import asyncio
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError
from .state import ResearchState
from .tools import fetch_papers, extract_constraints, write_report
from langchain_groq import ChatGroq
logger = logging.getLogger(__name__)


def exponential_backoff(max_retries: int = 4, base_delay: float = 1.0):
    def decorator(fn):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("[Retry %d/%d] %s — sleeping %.2fs", attempt+1, max_retries, exc, delay)
                    await asyncio.sleep(delay)
        return wrapper
    return decorator



PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research planning assistant.
Decompose the user query into an ordered task list for three agents: Retriever, Analyzer, Writer.
Return ONLY valid JSON:
{{"tasks": [{{"id": 1, "agent": "Retriever", "instruction": "...", "depends_on": []}}, ...]}}"""),
    ("human", "{user_prompt}"),
])


async def planner_node(state: ResearchState, llm: ChatGroq) -> dict:
    print("\n  [Planner] Decomposing query into task graph...")
    chain = PLANNER_PROMPT | llm
    raw = await _call_with_retry(chain, {"user_prompt": state["user_prompt"]})

    try:
        content = raw.content if hasattr(raw, "content") else str(raw)
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        tasks = json.loads(content).get("tasks", [])
        print(f"📋 [Planner] Plan ready: {len(tasks)} task(s)")
        return {"tasks": tasks, "stream_log": [f"Planner decomposed into {len(tasks)} tasks"]}
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Planner bad JSON — routing to fallback: %s", exc)
        fixed = await fallback_node({"bad_payload": raw.content}, llm)
        return {"tasks": fixed.get("tasks", []), "stream_log": ["FallbackAgent repaired planner output"]}


FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a JSON repair assistant.
Fix the broken JSON to match: {{"tasks":[{{"id":int,"agent":"Retriever|Analyzer|Writer","instruction":str,"depends_on":[int]}}]}}
Return ONLY valid JSON."""),
    ("human", "Broken payload:\n{bad_payload}"),
])


async def fallback_node(state: dict, llm: ChatGroq) -> dict:
    """Repairs malformed LLM JSON output — structural failure handler."""
    print("\n [Fallback] Repairing malformed JSON...")
    chain = FALLBACK_PROMPT | llm
    raw = await _call_with_retry(chain, {"bad_payload": state.get("bad_payload", "")})
    content = raw.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"tasks": []}

RETRIEVER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research retriever.
Fetch the top 3 relevant academic paper concepts for the query.
For each paper return: title, authors, year, and a 2-sentence abstract.
Format output clearly with numbered entries."""),
    ("human", "{instruction}"),
])


async def retriever_node(state: ResearchState, llm: ChatGroq) -> dict:
    """
    LangGraph node: retrieves paper concepts.
    Invokes the fetch_papers @tool explicitly, then calls LLM to elaborate.
    """
    task = _find_task(state["tasks"], "Retriever")
    instruction = task["instruction"] if task else state["user_prompt"]

    tool_result = fetch_papers.invoke({"query": instruction})
    print(f"\n📡 [Retriever] {tool_result}")

    chain = RETRIEVER_PROMPT | llm
    output = ""
    print("📡 [Retriever] Streaming papers...", end="", flush=True)
    async for chunk in chain.astream({"instruction": instruction}):
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        print(token, end="", flush=True)
        output += token
    print()
    return {"retriever_output": output, "stream_log": ["Retriever completed"]}

ANALYZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research analyst.
Given retrieved paper summaries, extract:
1. Core architectural constraints or innovations
2. Shared theoretical assumptions
3. Identified research gaps
Use bullet points. Be concise."""),
    ("human", "Papers:\n{retriever_output}\n\nTask:\n{instruction}"),
])


async def analyzer_node(state: ResearchState, llm: ChatGroq) -> dict:
    task = _find_task(state["tasks"], "Analyzer")
    instruction = task["instruction"] if task else "Extract constraints from the papers."

    tool_result = extract_constraints.invoke({"papers_text": state.get("retriever_output", "")})
    print(f"\n [Analyzer] {tool_result}")

    chain = ANALYZER_PROMPT | llm
    output = ""
    print(" [Analyzer] Streaming analysis...", end="", flush=True)
    async for chunk in chain.astream({
        "retriever_output": state.get("retriever_output", ""),
        "instruction": instruction,
    }):
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        print(token, end="", flush=True)
        output += token
    print()
    return {"analyzer_output": output, "stream_log": ["Analyzer completed"]}


WRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a scientific writer.
Given research analysis, write a publication-ready report section:
- Abstract (150-200 words)
- Novel architecture description (2-3 paragraphs)
- Future work (3 bullet points)
Use formal academic language."""),
    ("human", "Analysis:\n{analyzer_output}\n\nTask:\n{instruction}"),
])


async def writer_node(state: ResearchState, llm: ChatGroq) -> dict:
    task = _find_task(state["tasks"], "Writer")
    instruction = task["instruction"] if task else "Write the final research report."

    tool_result = write_report.invoke({"analysis_text": state.get("analyzer_output", "")})
    print(f"\n [Writer] {tool_result}")

    chain = WRITER_PROMPT | llm
    output = ""
    print(" [Writer] Streaming final report...", end="", flush=True)
    async for chunk in chain.astream({
        "analyzer_output": state.get("analyzer_output", ""),
        "instruction": instruction,
    }):
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        print(token, end="", flush=True)
        output += token
    print()
    return {"writer_output": output, "stream_log": ["Writer completed"]}


def _find_task(tasks: list[dict], agent_name: str) -> dict | None:
    return next((t for t in tasks if t.get("agent") == agent_name), None)


@exponential_backoff(max_retries=4, base_delay=1.0)
async def _call_with_retry(chain, inputs: dict):
    return await chain.ainvoke(inputs)
