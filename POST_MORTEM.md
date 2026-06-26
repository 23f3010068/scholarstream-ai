# POST_MORTEM.md

## Scaling Issue (Anticipated)
**Context Window Saturation:** As the DAG grows, each downstream node receives the full
accumulated state. Passing complete retriever + analyzer output to the Writer at scale
approaches token limits. Fix: add a summarisation node between Analyzer and Writer,
or implement vector-based context pruning.

## Design Change in Hindsight
**Static Edges → Conditional Routing:** Current LangGraph edges are fixed. In hindsight,
using `add_conditional_edges()` would allow the Planner to dynamically route to different
specialist nodes based on query type, making the topology adaptive.

## Trade-Offs — Manual Batcher vs LangGraph Parallelism
Chose explicit `asyncio.Semaphore(3)` batching over LangGraph's built-in parallel node
execution — guarantees API rate-limit safety and predictable latency at the cost of
not using LangGraph's native fan-out.

## Trade-Offs — Streaming Tokens vs Structured State
Chose `llm.astream()` per node for real-time UX over `llm.ainvoke()` with full structured
output — trades off strict schema validation mid-stream for better demo experience and
lower perceived latency.
