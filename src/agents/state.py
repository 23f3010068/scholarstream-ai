from __future__ import annotations
from typing import Annotated
from typing_extensions import TypedDict
import operator

class ResearchState(TypedDict):
    user_prompt:      str
    tasks:            list[dict]          # Planner output — ordered task list
    retriever_output: str                 # RetrieverNode output
    analyzer_output:  str                 # AnalyzerNode output
    writer_output:    str                 # WriterNode final report
    errors:           Annotated[list[str], operator.add]   # accumulate errors
    stream_log:       Annotated[list[str], operator.add]   # live status lines
