"""AmberClaw Agent Graph — LangGraph implementation of the logic loop.

This replaces the manual while-loop in AgentLoop with a state-driven graph.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
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


class AgentGraph:
    """Wrapper for the LangGraph compilation and execution."""

    def __init__(self, provider: Any, tools: List[Any], max_iterations: int = 10):
        self.provider = provider
        # Wrap tools as LangChain BaseTools
        self.tools = [t.to_langchain_tool() for t in tools]
        self.max_iterations = max_iterations
        self.runnable = self._build_graph()

    def _build_graph(self):
        """Construct the StateGraph."""
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("llm", self.llm_node)
        # ToolNode takes a list of LangChain tools
        workflow.add_node("tools", ToolNode(self.tools))

        # Define edges
        workflow.set_entry_point("llm")

        # Logic for tool routing
        workflow.add_conditional_edges(
            "llm", self.should_continue, {"continue": "tools", "end": END}
        )

        # Link tools back to LLM
        workflow.add_edge("tools", "llm")

        return workflow.compile()

    async def llm_node(self, state: AgentState) -> Dict[str, Any]:
        """Node for calling the LLM provider."""
        messages = state["messages"]
        iterations = state.get("iterations", 0)

        logger.debug("Graph: LLM node entry (iteration {})", iterations)

        # Convert LangChain messages to provider-agnostic dicts if needed
        # (LiteLLM usually takes dicts or LC messages)
        # We'll use the provider's chat_with_retry directly

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

        resp = await self.provider.chat_with_retry(
            messages=processed_msgs,
            tools=[tool.to_openai_tool() for tool in self.tools] if self.tools else None,
            model=state["config"].get("model"),
            **state["config"].get("llm_kwargs", {}),
        )

        # Convert response to AI Message
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
