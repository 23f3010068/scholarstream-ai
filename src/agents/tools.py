from __future__ import annotations
import aiohttp
import asyncio
from langchain_core.tools import tool
import asyncio
import aiohttp
from langchain_core.tools import tool


# @tool
# def fetch_papers(query: str) -> str:
#     """Fetches top 3 real academic papers from Semantic Scholar API for a research query."""
#     return asyncio.run(_fetch_semantic_scholar(query))


# async def _fetch_semantic_scholar(query: str) -> str:
#     url = "https://api.semanticscholar.org/graph/v1/paper/search"
#     params = {
#         "query": query,
#         "limit": 3,
#         "fields": "title,authors,year,abstract",
#     }
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
#                 if resp.status != 200:
#                     return f"[Semantic Scholar] API returned {resp.status} — falling back to simulation."
#                 data = await resp.json()
#                 papers = data.get("data", [])
#                 if not papers:
#                     return "[Semantic Scholar] No papers found for this query."
                
#                 result = []
#                 for i, paper in enumerate(papers, 1):
#                     title   = paper.get("title", "Unknown Title")
#                     authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
#                     year    = paper.get("year", "N/A")
#                     abstract = (paper.get("abstract") or "Abstract not available.")[:300] + "..."
#                     result.append(
#                         f"**Paper {i}:** {title}\n"
#                         f"**Authors:** {authors}\n"
#                         f"**Year:** {year}\n"
#                         f"**Abstract:** {abstract}\n"
#                     )
#                 return "\n---\n".join(result)
#     except Exception as exc:
#         return f"[Semantic Scholar] Request failed: {exc} — LLM will simulate papers instead."

@tool
async def fetch_papers(query: str) -> str:
    """Fetches top 3 real academic papers from Semantic Scholar API for a research query."""
    # Simply await the coroutine directly! No asyncio.run required.
    return await _fetch_semantic_scholar(query)


async def _fetch_semantic_scholar(query: str) -> str:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": 3,
        "fields": "title,authors,year,abstract",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return f"[Semantic Scholar] API returned {resp.status} — falling back to simulation."
                data = await resp.json()
                papers = data.get("data", [])
                if not papers:
                    return "[Semantic Scholar] No papers found for this query."
                
                result = []
                for i, paper in enumerate(papers, 1):
                    title   = paper.get("title", "Unknown Title")
                    authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                    year    = paper.get("year", "N/A")
                    abstract = (paper.get("abstract") or "Abstract not available.")[:300] + "..."
                    result.append(
                        f"**Paper {i}:** {title}\n"
                        f"**Authors:** {authors}\n"
                        f"**Year:** {year}\n"
                        f"**Abstract:** {abstract}\n"
                    )
                return "\n---\n".join(result)
    except Exception as exc:
        return f"[Semantic Scholar] Request failed: {exc} — LLM will simulate papers instead."

@tool
def extract_constraints(papers_text: str) -> str:
    """Extracts architectural constraints and research gaps from paper summaries."""
    return f"[Tool:extract_constraints] Received {len(papers_text)} chars — ready for LLM analysis."


@tool
def write_report(analysis_text: str) -> str:
    """Synthesizes analysis into a publication-ready academic report section."""
    return f"[Tool:write_report] Received {len(analysis_text)} chars — ready for LLM writing."