"""Turns a simple `handler(sender, text, send)` function into a BAND remote agent.

Agents only receive messages that @mention them, so every agent-to-agent
message below passes the other agent's name in `mentions`.
"""
import logging
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from band import Agent, configure_logging
from band.adapters import LangGraphAdapter
from band.runtime.formatters import strip_leading_mentions
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "agent_config.yaml"

# Names must match exactly what you typed when creating the agents in BAND.
DATA_NAME = os.environ.get("RADAR_DATA_NAME", "Radar Data")
BUILDER_NAME = os.environ.get("RADAR_BUILDER_NAME", "Radar Builder")
DESK_NAME = os.environ.get("RADAR_DESK_NAME", "Radar Desk")
AGENT_NAMES = {DATA_NAME, BUILDER_NAME, DESK_NAME}


def is_agent(name: str) -> bool:
    """True if the message came from one of our own agents (never auto-reply to these: avoids loops)."""
    return name.strip() in AGENT_NAMES

SENDER = re.compile(r"^\[(?P<sender>[^\]]+)\]:\s*(?P<text>.*)$", re.DOTALL)

Send = Callable[[str, list[str]], Awaitable[None]]
Handler = Callable[[str, str, Send], Awaitable[None]]


def write_config_from_env() -> None:
    """Build agent_config.yaml from Codespaces secrets (so keys never go in git)."""
    config = {}
    for key, id_var, key_var in [
        ("radar_data", "RADAR_DATA_ID", "RADAR_DATA_KEY"),
        ("radar_builder", "RADAR_BUILDER_ID", "RADAR_BUILDER_KEY"),
    ]:
        if os.environ.get(id_var) and os.environ.get(key_var):
            config[key] = {"agent_id": os.environ[id_var], "api_key": os.environ[key_var]}
    if config:
        CONFIG.write_text(yaml.safe_dump(config))


def run_agent(config_key: str, handler: Handler) -> None:
    import asyncio

    configure_logging(logging.INFO)
    write_config_from_env()
    if not CONFIG.exists():
        raise SystemExit(
            "agent_config.yaml not found. Add RADAR_DATA_ID / RADAR_DATA_KEY / "
            "RADAR_BUILDER_ID / RADAR_BUILDER_KEY as Codespaces secrets."
        )
    checkpointer = InMemorySaver()

    def graph_factory(band_tools: list[Any]):
        send_message = next(t for t in band_tools if t.name == "band_send_message")

        async def send(content: str, mentions: list[str]) -> None:
            await send_message.ainvoke({"content": content, "mentions": mentions})

        async def on_message(state: MessagesState) -> dict:
            if not state["messages"]:
                return {"messages": []}
            content = str(state["messages"][-1].content)
            match = SENDER.match(content)
            sender = match.group("sender") if match else ""
            text = strip_leading_mentions(match.group("text") if match else content).strip()
            try:
                await handler(sender, text, send)
            except Exception as err:  # tell the room instead of crashing silently
                logging.exception("handler failed")
                if sender and not is_agent(sender):
                    await send(f"Sorry, something went wrong: {err}", [sender])
            return {"messages": []}

        graph = StateGraph(MessagesState)
        graph.add_node("on_message", on_message)
        graph.add_edge(START, "on_message")
        graph.add_edge("on_message", END)
        return graph.compile(checkpointer=checkpointer)

    async def main() -> None:
        adapter = LangGraphAdapter(graph_factory=graph_factory)
        agent = Agent.from_config(config_key, adapter=adapter)
        await agent.run()

    asyncio.run(main())


def parse_command(text: str) -> dict:
    """'DATA_READY BMATS101 days=5 round=1 requested_by=Ganesh K' -> dict."""
    # remove any @mentions of our agents (names have spaces, so do it explicitly)
    for name in AGENT_NAMES:
        text = text.replace(f"@{name}", " ")
    text = text.strip()
    for leftover in {n.split()[-1] for n in AGENT_NAMES}:  # e.g. "Builder DATA_READY ..."
        if text.split(" ", 1)[0] == leftover:
            text = text.split(" ", 1)[1] if " " in text else ""
    # drop the human-readable summary we append in brackets: "... (3 papers, 40 questions)"
    text = re.sub(r"\s*\([^()]*\)\s*$", "", text)
    requested_by = ""
    if " requested_by=" in text:
        text, requested_by = text.split(" requested_by=", 1)
    words = text.split()
    cmd = {"action": words[0].upper().rstrip(":") if words else "", "args": [],
           "requested_by": requested_by.strip()}
    for w in words[1:]:
        if "=" in w:
            k, v = w.split("=", 1)
            cmd[k.lower()] = v
        else:
            cmd["args"].append(w)
    return cmd
