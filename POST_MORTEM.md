# POST_MORTEM.md — ScholarStream AI

## Scaling Issue (Anticipated)

**Context Window Saturation vs. Cost**

As the DAG expands (e.g., 10+ tasks, each passing its full output downstream),
late-stage agents accumulate a growing context window.  Passing the complete
execution history to the Writer agent at step 10 can easily approach 100k tokens,
increasing cost quadratically and risking context-limit errors.

**Solution:** Insert an explicit summarisation step between agent handoffs
(or a vector-pruning step that embeds intermediate outputs and retrieves only
the top-k most relevant chunks before passing context to the next agent).

---

## Design Change in Hindsight

**Sequential Dependency Arrays → Event-Driven Async Bus**

The current rigid `depends_on` integer array requires the full DAG to be known
at planning time.  In hindsight, replacing this with an `asyncio.Queue`-based
event broker — where each agent *emits* a typed event when its data is ready,
and downstream agents *subscribe* to those event types — would allow dynamic,
emergent topologies where the Planner can inject new tasks mid-flight without
restarting the pipeline.

---

## Trade-Off 1 — Custom Batching vs. Dynamic Worker Pools

| Chosen Approach | Alternative |
|---|---|
| `asyncio.Semaphore(3)` — hard cap on concurrent workers | Elastic worker pool that scales with API quota headers |

**Reasoning:** A fixed semaphore guarantees absolute rate-limit safety and
predictable latency SLAs at the cost of leaving headroom on the table during
low-load periods.  For an academic submission where stability > throughput,
this is the correct trade-off.

---

## Trade-Off 2 — Strict JSON Schema Enforcement vs. Creative Agility

| Chosen Approach | Alternative |
|---|---|
| Pydantic models + JSON-mode on every LLM call | Free-text outputs parsed with regex |

**Reasoning:** Strict schema enforcement means the Writer agent can never
"drift" into an unstructured format that breaks downstream parsers.  The cost
is that the Writer's output is more template-constrained and less organically
creative.  For a system that must compose with other programs (report renderers,
vector DBs), reliability outweighs flexibility.
