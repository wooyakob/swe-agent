from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from agent.common.entities import SEEngagementPlan


class SEDiscoveryState(BaseModel):
    discovery_next_step: Optional[str] = Field(None, description="The next discovery research step to conduct")
    engagement_plan: Optional[SEEngagementPlan] = Field(None, description="The SE engagement plan to be executed")
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages] = Field(
        [], description="Running scratchpad of discovery research messages"
    )
    is_valid_research_step: Optional[bool] = Field(None, description="Whether the current research step is valid")
