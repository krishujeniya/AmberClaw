"""AmberClaw Agent Graph — LangGraph implementation of the logic loop.

This replaces the manual while-loop in AgentLoop with a state-driven graph.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from loguru import logger


class AgentState(TypedDict):
    """The state maintained throughout the agentic loop."""

    # messages list, with 'append' logic for state merging
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Track iterations to prevent infinite loops
    iterations: int

    # Target config for nodes to use
    config: Dict[str, Any]

    # Agent loop mode
    mode: str

    # Plan for plan_and_execute mode
    plan: list[str]

    # Sub-task state
    current_task: str | None


class AgentGraph:
    """Wrapper for the LangGraph compilation and execution."""

    def __init__(self, provider: Any, tools: List[Any], max_iterations: int = 10, mode: str = "react"):
        self.provider = provider
        # Wrap tools as LangChain BaseTools
        self.tools = [t.to_langchain_tool() for t in tools]
        self.max_iterations = max_iterations
        self.mode = mode
        self.runnable = self._build_graph()

    def _build_graph(self):
        """Construct the StateGraph based on mode."""
        workflow = StateGraph(AgentState)

        if self.mode == "plan_and_execute":
            workflow.add_node("planner", self.planner_node)
            workflow.add_node("executor", self.llm_node)
            workflow.add_node("tools", ToolNode(self.tools))
            workflow.add_node("reflect", self.reflect_node)

            workflow.set_entry_point("planner")
            workflow.add_edge("planner", "executor")
            workflow.add_conditional_edges("executor", self.should_continue, {"continue": "tools", "end": "reflect"})
            workflow.add_edge("tools", "executor")
            workflow.add_conditional_edges("reflect", self.reflect_router, {"replan": "planner", "end": END})
        elif self.mode == "react_reflect":
            workflow.add_node("llm", self.llm_node)
            workflow.add_node("tools", ToolNode(self.tools))
            workflow.add_node("reflect", self.reflect_node)

            workflow.set_entry_point("llm")
            workflow.add_conditional_edges("llm", self.should_continue, {"continue": "tools", "end": "reflect"})
            workflow.add_edge("tools", "llm")
            workflow.add_conditional_edges("reflect", self.reflect_router, {"replan": "llm", "end": END})
        elif self.mode == "simple":
            workflow.add_node("llm", self.llm_node)
            workflow.set_entry_point("llm")
            workflow.add_edge("llm", END)
        else: # default react
            workflow.add_node("llm", self.llm_node)
            workflow.add_node("tools", ToolNode(self.tools))
            workflow.set_entry_point("llm")
            workflow.add_conditional_edges("llm", self.should_continue, {"continue": "tools", "end": END})
            workflow.add_edge("tools", "llm")

        return workflow.compile()

    async def _call_llm_with_state(self, state: AgentState, prompt_modifier: str | None = None) -> AIMessage:
        messages = list(state["messages"])
        if prompt_modifier:
            messages.append(SystemMessage(content=prompt_modifier))

        processed_msgs = []
        for m in messages:
            if isinstance(m, HumanMessage):
                processed_msgs.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                processed_msgs.append(
                    {
                        "role": "assistant",
                        "content": m.content,
                        "tool_calls": m.additional_kwargs.get("tool_calls"),
                    }
                )
            elif isinstance(m, ToolMessage):
                processed_msgs.append(
                    {"role": "tool", "content": m.content, "tool_call_id": m.tool_call_id}
                )
            elif isinstance(m, SystemMessage):
                processed_msgs.append({"role": "system", "content": m.content})

        resp = await self.provider.chat_with_retry(
            messages=processed_msgs,
            tools=[tool.to_openai_tool() for tool in self.tools] if self.tools and self.mode != "simple" else None,
            model=state["config"].get("model"),
            **state["config"].get("llm_kwargs", {}),
        )

        ai_msg = AIMessage(content=resp.content or "")
        if resp.tool_calls:
            ai_msg.additional_kwargs["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": str(tc.arguments)},
                }
                for tc in resp.tool_calls
            ]
        return ai_msg

    async def planner_node(self, state: AgentState) -> Dict[str, Any]:
        """Create a plan for the user request."""
        logger.debug("Graph: Planner node entry")
        prompt = "Create a detailed step-by-step plan to satisfy the user request. Output a numbered list of steps."
        resp = await self._call_llm_with_state(state, prompt_modifier=prompt)
        # Parse plan out of text (simple approach for now)
        plan = [line.strip() for line in str(resp.content).split("\\n") if line.strip() and line[0].isdigit()]
        return {"plan": plan, "iterations": state.get("iterations", 0) + 1, "messages": [resp]}

    async def reflect_node(self, state: AgentState) -> Dict[str, Any]:
        """Evaluate the previous output and self-correct if needed."""
        logger.debug("Graph: Reflect node entry")
        prompt = "Reflect on your previous responses. Are they correct, complete, and safe? If yes, respond 'PASS'. If no, respond 'FAIL' with reasons and a corrected plan."
        resp = await self._call_llm_with_state(state, prompt_modifier=prompt)
        return {"messages": [resp], "iterations": state.get("iterations", 0) + 1}

    def reflect_router(self, state: AgentState) -> str:
        """Decide whether to replan/re-execute based on reflection."""
        last_message = state["messages"][-1]
        content = str(last_message.content).upper()
        if "FAIL" in content and state["iterations"] < self.max_iterations:
            return "replan"
        return "end"

    async def llm_node(self, state: AgentState) -> Dict[str, Any]:
        """Node for calling the LLM provider."""
        iterations = state.get("iterations", 0)
        logger.debug("Graph: LLM node entry (iteration {})", iterations)

        prompt = None
        if self.mode == "plan_and_execute" and state.get("plan"):
            prompt = f"Current Plan: {state['plan']}. Execute the next logical step."

        ai_msg = await self._call_llm_with_state(state, prompt_modifier=prompt)
        return {"messages": [ai_msg], "iterations": iterations + 1}

    def should_continue(self, state: AgentState) -> str:
        """Route to tools or end."""
        messages = state["messages"]
        last_message = messages[-1]

        if state["iterations"] >= self.max_iterations:
            logger.warning("Graph: Max iterations reached")
            return "end"

        if isinstance(last_message, AIMessage) and last_message.additional_kwargs.get("tool_calls"):
            return "continue"

        return "end"
