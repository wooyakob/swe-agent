from agent.architect.graph import se_discovery
from agent.common.entities import SEEngagementPlan
from agent.developer.graph import se_poc_demo
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages, StateGraph, START, END
from typing import Annotated, Optional


class SEAgentState(BaseModel):
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    engagement_plan: Optional[SEEngagementPlan] = Field(None, description="The SE engagement plan to execute")


def create_workflow_graph():
    graph_builder = StateGraph(SEAgentState)

    graph_builder.add_node("se_discovery", se_discovery)
    graph_builder.add_node("se_poc_demo", se_poc_demo)

    graph_builder.add_edge(START, "se_discovery")
    graph_builder.add_edge("se_discovery", "se_poc_demo")
    graph_builder.add_edge("se_poc_demo", END)

    return graph_builder


se_agent = create_workflow_graph().compile().with_config({"tags": ["se-agent-v1"], "recursion_limit": 200})
