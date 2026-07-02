from typing import Annotated, List, Optional

from langgraph.graph.message import Messages

from agent.common.entities import SEEngagementPlan
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class DiffTask(BaseModel):
    original_code_snippet: str = Field(
        description="The exact code or text snippet being replaced, copied verbatim from the file (with line numbers)"
    )
    task_description: str = Field(
        description="How the snippet should be changed, with full concrete instructions"
    )


class Diffs(BaseModel):
    diffs: List[DiffTask] = Field(description="Instructions on how to change the file content")


def add_messages_with_clear(left: Messages, right: Messages) -> Messages:
    if right is None or not right:
        return []
    return add_messages(left, right)


class SEPOCState(BaseModel):
    engagement_plan: Optional[SEEngagementPlan] = Field(None, description="The SE engagement plan to execute")
    current_task_idx: Optional[int] = Field(0, description="Current artifact index in the engagement plan")
    current_atomic_task_idx: Optional[int] = Field(0, description="Current step index within the current artifact")
    diffs: Optional[Diffs] = Field(None, description="Diffs to apply to the current artifact file")
    atomic_implementation_research: Annotated[list[AnyMessage], add_messages_with_clear]
    codebase_structure: Optional[str] = Field(None, description="Current poc_workspace file structure")
    current_file_content: Optional[str] = Field(None, description="Current content of the artifact file being edited")
