"""RADAR DATA - reads VTU past papers + syllabus + live web info, hands data to the Builder.

Messages it understands:
  analyse <CODE> [days=N] [req=<id>]                (from a student in BAND, or from Radar Desk)
  NEED_MORE <CODE> modules=3,5 req=<id> round=1 ... (from Radar Builder)

Loop safety: it never auto-replies to messages from other agents unless they are a known command.
"""
import asyncio

from radar import analysis
from radar.band_helper import BUILDER_NAME, DATA_NAME, is_agent, parse_command, run_agent


async def handle(sender: str, text: str, send) -> None:
    cmd = parse_command(text)
    action = cmd["action"]
    req = cmd.get("req", "")
    human = sender and not is_agent(sender)
    if analysis.is_stale(req):
        return  # old message re-delivered after a restart: skip it

    if action in ("ANALYSE", "ANALYZE"):
        if not cmd["args"]:
            if human:
                await send("Tell me a subject code, e.g. `analyse BMATS101 days=5`", [sender])
            return
        code = cmd["args"][0].upper()
        days = cmd.get("days", "5")
        requester = cmd["requested_by"] or (sender if human else "")
        if human:
            await send(f"On it! Reading the {code} question papers and checking the web for updates...", [sender])
        analysis.log_message(code, DATA_NAME, "papers + web", f"Reading every {code} past paper and checking vtu.ac.in for updates.", req)

        dataset = await asyncio.to_thread(analysis.collect, code)
        summary = (f"{len(dataset['papers'])} papers, {len(dataset['questions'])} questions, "
                   f"{len(dataset['live']['notes'])} live notes")
        analysis.log_message(code, DATA_NAME, BUILDER_NAME, f"Collected {summary}. Please build the plan.", req)
        msg = f"DATA_READY {code} days={days} round=1 req={req} requested_by={requester}"
        await send(f"@{BUILDER_NAME} {msg}  ({summary})", [BUILDER_NAME])

    elif action == "NEED_MORE":
        if not cmd["args"]:
            return
        code = cmd["args"][0].upper()
        modules = [int(m) for m in cmd.get("modules", "").split(",") if m.strip().isdigit()]
        requester = cmd["requested_by"]

        dataset = await asyncio.to_thread(analysis.enrich, code, modules)
        added = len(dataset["web_questions"])
        analysis.log_message(code, DATA_NAME, BUILDER_NAME,
                             f"Searched the web: found {added} extra questions for Module(s) {', '.join(map(str, modules))}.", req)
        msg = f"DATA_READY {code} days={cmd.get('days', '5')} round=2 req={req} requested_by={requester}"
        await send(f"@{BUILDER_NAME} {msg}  (+{added} web questions)", [BUILDER_NAME])

    elif human:
        await send("I'm Radar Data. Try: `analyse <SUBJECT_CODE> days=5`", [sender])
    # messages from other agents that are not commands are ignored on purpose (no reply loops)


if __name__ == "__main__":
    run_agent("radar_data", handle)
