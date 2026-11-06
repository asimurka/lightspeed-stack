"""Typed bag of LCS fields collected during a PAI agent run.

Intended as the ``deps`` object passed into ``Agent.run``. Capabilities mutate
the same instance; after the run, projection reads it.

"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.common.turn_summary import ReferencedDocument

type AgentRunContextStatus = Literal["full", "compacted"]
"""Whether agent history for this run was compacted."""


class AgentRunDeps(BaseModel):
    """Mutable per-run collector for custom capability results.

    Pass one instance to ``Agent.run(deps=...)``. Capabilities write fields in
    place; the caller inspects the same object after the run.

    Attributes:
        context_status: Whether agent history was full or compacted.
        referenced_documents: Documents inlined into the run (auto RAG).

    """

    model_config = ConfigDict(extra="forbid")

    context_status: AgentRunContextStatus = Field(
        default="full",
        description="Whether agent history for this run was full or compacted",
    )
    referenced_documents: list[ReferencedDocument] = Field(
        default_factory=list,
        description="Documents inlined into the run by capabilities",
    )
