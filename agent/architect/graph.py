import json
import os
from typing import List, TypedDict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.constants import END, START
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph

from agent.architect.state import SEDiscoveryState
from agent.tools.couchbase_knowledge import couchbase_tools
from agent.tools.write import get_files_structure
from helpers.prompts import markdown_to_prompt_template
from agent.common.entities import SEEngagementPlan


class DiscoveryStep(BaseModel):
    reasoning: str = Field(description="Why this research direction is valuable for this customer engagement")
    hypothesis: str = Field(description="The specific aspect of Couchbase or the customer's use case to research next")


class DiscoveryEvaluation(BaseModel):
    reasoning: str = Field(description="Why the proposed research step is valid or redundant (1-3 sentences)")
    is_valid: bool = Field(description="Whether this research step adds material new value")


# prompts
plan_next_step_prompt = markdown_to_prompt_template("agent/architect/prompts/plan_next_step_prompt.md")
check_research_prompt = markdown_to_prompt_template("agent/architect/prompts/check_research_already_explored.md")
conduct_research_prompt = markdown_to_prompt_template("agent/architect/prompts/conduct_research_plan_prompt.md")
extract_plan_prompt = markdown_to_prompt_template("agent/architect/prompts/extract_implementation_plan.md")

# runnables
plan_next_step_runnable = plan_next_step_prompt | ChatAnthropic(model="claude-sonnet-4-20250514").with_structured_output(DiscoveryStep)
check_research_runnable = check_research_prompt | ChatAnthropic(model="claude-sonnet-4-20250514").with_structured_output(DiscoveryEvaluation)
conduct_research_runnable = conduct_research_prompt | ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(couchbase_tools)
extract_plan_runnable = extract_plan_prompt | ChatAnthropic(model="claude-sonnet-4-20250514") | JsonOutputParser(pydantic_object=SEEngagementPlan)

tool_node = ToolNode(couchbase_tools, messages_key="implementation_research_scratchpad")


def _poc_workspace_structure() -> str:
    poc_dir = "./poc_workspace"
    os.makedirs(poc_dir, exist_ok=True)
    return get_files_structure.invoke({"directory": poc_dir})


class ComeUpWithDiscoveryNextStepOutput(TypedDict):
    discovery_next_step: str
    implementation_research_scratchpad: List[AnyMessage]


def come_up_with_research_next_step(state: SEDiscoveryState) -> ComeUpWithDiscoveryNextStepOutput:
    response = plan_next_step_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "poc_workspace_structure": _poc_workspace_structure(),
    })
    return {
        "discovery_next_step": response.hypothesis,
        "implementation_research_scratchpad": [
            AIMessage(content=(
                f"My next research direction: {response.hypothesis}\n"
                f"Rationale: {response.reasoning}"
            ))
        ],
    }


class CheckResearchStepOutput(TypedDict):
    is_valid_research_step: bool
    implementation_research_scratchpad: List[AnyMessage]


def check_research_step(state: SEDiscoveryState) -> CheckResearchStepOutput:
    response = check_research_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad
    })
    if not response.is_valid:
        return {
            "is_valid_research_step": False,
            "implementation_research_scratchpad": [
                HumanMessage(content="This research direction is redundant or off-topic: " + response.reasoning)
            ],
        }
    return {
        "is_valid_research_step": True,
        "implementation_research_scratchpad": [
            HumanMessage(content="Research direction approved. Proceed with investigation.")
        ],
    }


def conduct_research(state: SEDiscoveryState):
    response = conduct_research_runnable.invoke({
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "poc_workspace_structure": _poc_workspace_structure(),
    })
    return {"implementation_research_scratchpad": [response]}


def convert_tools_messages_to_ai_and_human(scratchpad: List[AnyMessage]):
    messages = []
    for message in scratchpad:
        if message.type == "ai":
            if message.tool_calls:
                calls = [
                    f"Called tool {tc['name']} with args: {json.dumps(tc['args'])}"
                    for tc in message.tool_calls
                ]
                messages.append(AIMessage(content="\n".join(calls)))
            else:
                messages.append(message)
        elif message.type == "tool":
            messages.append(HumanMessage(content=f"Tool {message.name} returned: {message.content}"))
        else:
            messages.append(message)
    return messages


def extract_engagement_plan(state: SEDiscoveryState):
    response = extract_plan_runnable.invoke({
        "research_findings": convert_tools_messages_to_ai_and_human(state.implementation_research_scratchpad),
        "poc_workspace_structure": _poc_workspace_structure(),
        "output_format": JsonOutputParser(pydantic_object=SEEngagementPlan).get_format_instructions(),
    })
    plan = SEEngagementPlan(**response)
    return {"engagement_plan": plan}


def should_call_tool(state: SEDiscoveryState):
    last_message = state.implementation_research_scratchpad[-1]
    if last_message.tool_calls:
        return "should_call_tool"
    return "extract_plan"


def should_conduct_research(state: SEDiscoveryState):
    if state.is_valid_research_step:
        return "plan_is_valid"
    return "plan_is_not_valid"


class SEDiscoveryInput(TypedDict):
    implementation_research_scratchpad: List[AnyMessage]


class SEDiscoveryOutput(TypedDict):
    engagement_plan: Optional[SEEngagementPlan]


workflow = StateGraph(SEDiscoveryState, input=SEDiscoveryInput, output=SEDiscoveryOutput)

workflow.add_node("come_up_with_research_next_step", come_up_with_research_next_step)
workflow.add_node("check_research_step", check_research_step)
workflow.add_node("conduct_research", conduct_research)
workflow.add_node("extract_engagement_plan", extract_engagement_plan)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "come_up_with_research_next_step")
workflow.add_edge("come_up_with_research_next_step", "check_research_step")
workflow.add_conditional_edges(
    "check_research_step",
    should_conduct_research,
    {
        "plan_is_valid": "conduct_research",
        "plan_is_not_valid": "come_up_with_research_next_step",
    },
)
workflow.add_conditional_edges(
    "conduct_research",
    should_call_tool,
    {
        "should_call_tool": "tools",
        "extract_plan": "extract_engagement_plan",
    },
)
workflow.add_edge("tools", "conduct_research")
workflow.add_edge("extract_engagement_plan", END)

se_discovery = workflow.compile().with_config({"tags": ["se-discovery-v1"]})
