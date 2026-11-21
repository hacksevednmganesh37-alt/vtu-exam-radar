"""RADAR DATA - reads VTU past papers + syllabus + live web info, hands data to the Builder.

Talk to it in a BAND room:
  @Radar Data analyse BMATS101 days=5

Messages it understands:
  analyse <CODE> [days=N]                         (from a human)
  NEED_MORE <CODE> modules=3,5 days=N round=1 ... (from Radar Builder)
"""
import asyncio

from radar import analysis
from radar.band_helper import BUILDER_NAME, DATA_NAME, parse_command, run_agent


async def handle(sender: str, text: str, send) -> None:
    cmd = parse_command(text)
    action = cmd["action"]

    if action in ("ANALYSE", "ANALYZE"):
        if not cmd["args"]:
            await send("Tell me a subject code, e.g. `analyse BMATS101 days=5`", [sender])
            return
        code = cmd["args"][0].upper()
        days = cmd.get("days", "5")
        await send(f"On it! Reading the {code} question papers and checking the web for updates...", [sender])

        dataset = await asyncio.to_thread(analysis.collect, code)
        summary = (f"{len(dataset['papers'])} papers, {len(dataset['questions'])} questions, "
                   f"{len(dataset['live']['notes'])} live notes")
        msg = f"DATA_READY {code} days={days} round=1 requested_by={sender}"
        analysis.log_message(code, DATA_NAME, BUILDER_NAME, f"Collected {summary}. Please build the dashboard.")
        await send(f"@{BUILDER_NAME} {msg}  ({summary})", [BUILDER_NAME])

    elif action == "NEED_MORE":
        code = cmd["args"][0].upper()
        modules = [int(m) for m in cmd.get("modules", "").split(",") if m.strip().isdigit()]
        requester = cmd["requested_by"]
        await send(f"Searching the web for more Module {', '.join(map(str, modules))} questions...",
                   [requester] if requester else [])

        dataset = await asyncio.to_thread(analysis.enrich, code, modules)
        added = len(dataset["web_questions"])
        analysis.log_message(code, DATA_NAME, BUILDER_NAME,
                             f"Found {added} extra web questions for modules {modules}. Data complete.")
        msg = f"DATA_READY {code} days={cmd.get('days', '5')} round=2 requested_by={requester}"
        await send(f"@{BUILDER_NAME} {msg}  (+{added} web questions)", [BUILDER_NAME])

    else:
        await send("I'm Radar Data. Try: `analyse <SUBJECT_CODE> days=5`", [sender] if sender else [])


if __name__ == "__main__":
    run_agent("radar_data", handle)
