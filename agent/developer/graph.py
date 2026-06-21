import json
import os
import re
from typing import List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from helpers.prompts import markdown_to_prompt_template
from agent.developer.state import SEPOCState, Diffs
from langgraph.prebuilt import ToolNode
from agent.tools.couchbase_knowledge import couchbase_tools
from agent.tools.write import get_files_structure

extract_diffs_tasks_prompt = markdown_to_prompt_template("agent/developer/prompts/create_diff_prompt.md")
implement_diffs_prompt = markdown_to_prompt_template("agent/developer/prompts/implement_diff.md")
implement_new_file_prompt = markdown_to_prompt_template("agent/developer/prompts/implement_new_file.md")

extract_diff_runnable = extract_diffs_tasks_prompt | ChatAnthropic(model="claude-sonnet-4-20250514") | StrOutputParser()
edit_according_to_diff_runnable = implement_diffs_prompt | ChatAnthropic(model="claude-sonnet-4-20250514") | StrOutputParser()
create_new_file_runnable = implement_new_file_prompt | ChatAnthropic(model="claude-sonnet-4-20250514") | StrOutputParser()

get_clear_plan_prompt = markdown_to_prompt_template("agent/developer/prompts/get_clear_implementation_plan.md")
get_clear_plan_runnable = get_clear_plan_prompt | ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(couchbase_tools)


def _poc_workspace_structure() -> str:
    poc_dir = "./poc_workspace"
    os.makedirs(poc_dir, exist_ok=True)
    return get_files_structure.invoke({"directory": poc_dir})


def start_implementing(state: SEPOCState):
    return {"current_task_idx": 0, "current_atomic_task_idx": 0}


def proceed_to_next_atomic_task(state: SEPOCState):
    current_task_idx = state.current_task_idx
    current_atomic_task_idx = state.current_atomic_task_idx
    plan = state.engagement_plan
    current_artifact = plan.artifacts[current_task_idx]
    poc_steps = current_artifact.poc_steps

    if current_atomic_task_idx >= len(poc_steps) - 1:
        return {"current_task_idx": current_task_idx + 1, "current_atomic_task_idx": 0}
    return {"current_task_idx": current_task_idx, "current_atomic_task_idx": current_atomic_task_idx + 1}


def get_clear_implementation_plan_for_atomic_task(state: SEPOCState):
    current_artifact = state.engagement_plan.artifacts[state.current_task_idx]
    current_step = current_artifact.poc_steps[state.current_atomic_task_idx]
    result = get_clear_plan_runnable.invoke({
        "development_task": current_step.poc_step,
        "file_content": state.current_file_content,
        "target_file": current_artifact.file_path,
        "codebase_structure": state.codebase_structure,
        "additional_context": current_step.additional_context,
        "atomic_implementation_research": state.atomic_implementation_research,
    })
    return {"atomic_implementation_research": [result]}


def should_continue_implementation_research(state: SEPOCState):
    last_research_step = state.atomic_implementation_research[-1]
    if last_research_step.tool_calls:
        return "should_continue_research"
    return "implement_plan"


def prepare_for_implementation(state: SEPOCState):
    current_artifact = state.engagement_plan.artifacts[state.current_task_idx]
    file_path = current_artifact.file_path
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, "r") as f:
            file_content = f.read()
    except FileNotFoundError:
        file_content = ""

    return {
        "current_file_content": file_content,
        "codebase_structure": _poc_workspace_structure(),
        "atomic_implementation_research": None,
    }


def is_implementation_complete(state: SEPOCState):
    if state.current_task_idx >= len(state.engagement_plan.artifacts):
        return END
    return "continue"


def convert_tools_messages_to_ai_and_human(scratchpad: List[AnyMessage]):
    messages = []
    for message in scratchpad:
        if message.type == "ai":
            if message.tool_calls:
                tool_name = message.tool_calls[0]["name"]
                tool_args = json.dumps(message.tool_calls[0]["args"])
                messages.append(AIMessage(content=f"Called tool {tool_name} with args: {tool_args}"))
            else:
                messages.append(message)
        elif message.type == "tool":
            messages.append(HumanMessage(content=f"Tool {message.name} returned: {message.content}"))
        else:
            messages.append(message)
    return messages


def creating_diffs_for_task(state: SEPOCState):
    current_artifact = state.engagement_plan.artifacts[state.current_task_idx]
    current_step = current_artifact.poc_steps[state.current_atomic_task_idx]
    file_path = current_artifact.file_path

    os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else ".", exist_ok=True)

    if not os.path.exists(file_path):
        new_file_content = create_new_file_runnable.invoke({
            "task": current_step.poc_step,
            "additional_context": current_step.additional_context,
            "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
            "file_path": file_path,
        })
        with open(file_path, "w") as f:
            f.write(new_file_content)
            f.flush()
    else:
        with open(file_path, "r") as f:
            file_content = f.read()

        lines = [f"{i}| {line}" for i, line in enumerate(file_content.splitlines(), start=1)]
        numbered_content = "\n".join(lines)

        diffs_tasks = extract_diff_runnable.invoke({
            "task": current_step.poc_step,
            "additional_context": current_step.additional_context,
            "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
            "file_path": file_path,
            "file_content": numbered_content,
            "output_format": JsonOutputParser(pydantic_object=Diffs).get_format_instructions(),
        })

        blocks = re.findall(r"<code_change_request>(.*?)</code_change_request>", diffs_tasks, re.DOTALL)
        for block in blocks:
            match = re.search(
                r"original_code_snippet:\s*(.*?)\s*edit_code_snippet:\s*(.*)",
                block,
                re.DOTALL,
            )
            if match:
                with open(file_path, "r") as f:
                    file_content = f.read()
                original_code = match.group(1).strip()
                edited_code = match.group(2).strip()
                orig_lines = original_code.splitlines()
                first_line = int(orig_lines[0].split("|")[0].strip())
                last_line = int(orig_lines[-1].split("|")[0].strip())
                new_content = file_content.splitlines()
                new_content = new_content[: first_line - 1] + edited_code.splitlines() + new_content[last_line:]
                with open(file_path, "w") as f:
                    f.write("\n".join(new_content))
                    f.flush()


research_tool_node = ToolNode(couchbase_tools, messages_key="atomic_implementation_research")

workflow = StateGraph(SEPOCState)

workflow.add_node("start_implementing", start_implementing)
workflow.add_node("prepare_for_implementation", prepare_for_implementation)
workflow.add_node("proceed_to_next_atomic_task", proceed_to_next_atomic_task)
workflow.add_node("get_clear_implementation_plan_for_atomic_task", get_clear_implementation_plan_for_atomic_task)
workflow.add_node("research_tool_node", research_tool_node)
workflow.add_node("creating_diffs_for_task", creating_diffs_for_task)

workflow.add_edge(START, "start_implementing")
workflow.add_edge("start_implementing", "prepare_for_implementation")
workflow.add_edge("prepare_for_implementation", "get_clear_implementation_plan_for_atomic_task")
workflow.add_conditional_edges(
    "get_clear_implementation_plan_for_atomic_task",
    should_continue_implementation_research,
    {
        "should_continue_research": "research_tool_node",
        "implement_plan": "creating_diffs_for_task",
    },
)
workflow.add_edge("research_tool_node", "get_clear_implementation_plan_for_atomic_task")
workflow.add_edge("creating_diffs_for_task", "proceed_to_next_atomic_task")
workflow.add_conditional_edges(
    "proceed_to_next_atomic_task",
    is_implementation_complete,
    {
        "continue": "prepare_for_implementation",
        END: END,
    },
)

se_poc_demo = workflow.compile().with_config({"tags": ["se-poc-demo-v1"]})
