"""RADAR BUILDER - checks the data, asks Radar Data for more if needed, builds + publishes the dashboard.

Messages it understands:
  DATA_READY <CODE> days=N round=1|2 requested_by=<name>   (from Radar Data)
  build <CODE> [days=N]                                     (from a human, skips the gap check)
"""
import asyncio
import os

from radar import analysis
from radar.band_helper import BUILDER_NAME, DATA_NAME, parse_command, run_agent

SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
PUSH = os.environ.get("PUBLISH_PUSH", "1") == "1"   # set to 0 to skip git push while testing


async def build_and_publish(code: str, days: int, requester: str, send) -> None:
    analysis.log_message(code, BUILDER_NAME, requester or "students", "Building the dashboard and publishing it.")
    report = await asyncio.to_thread(analysis.build_report, code, days)
    await asyncio.to_thread(analysis.publish, report, PUSH)

    top = report["repeated_questions"][:3]
    top_text = "\n".join(f"- {r['question']} (asked {r['times']}x)" for r in top) or "- (no repeats found)"
    best = max(report["modules"], key=lambda m: m["share"])
    link = f"{SITE_URL}/?subject={code}" if SITE_URL else f"site/data/{code}.json"
    await send(
        f"Dashboard ready for {report['subject_name']} ({code})!\n"
        f"Highest-weight module: Module {best['number']} ({best['share']:.0%} of marks)\n"
        f"Top repeated questions:\n{top_text}\n"
        f"Full {days}-day plan: {link}",
        [requester] if requester else [],
    )


async def handle(sender: str, text: str, send) -> None:
    cmd = parse_command(text)
    action = cmd["action"]

    if action == "DATA_READY":
        code = cmd["args"][0].upper()
        days = int(cmd.get("days", 5))
        round_no = int(cmd.get("round", 1))
        requester = cmd["requested_by"]

        dataset = analysis.load_dataset(code)
        gaps = analysis.find_gaps(dataset)
        if gaps and round_no == 1:
            # Agent-to-agent step: Builder can't judge thin modules, so it asks Data for more.
            gap_text = ",".join(map(str, gaps))
            analysis.log_message(code, BUILDER_NAME, DATA_NAME,
                                 f"Modules {gap_text} have too few questions to rank. Please find more.")
            await send(
                f"@{DATA_NAME} NEED_MORE {code} modules={gap_text} days={days} round=1 requested_by={requester}",
                [DATA_NAME],
            )
            return
        await build_and_publish(code, days, requester, send)

    elif action == "BUILD":
        if not cmd["args"]:
            await send("Tell me a subject code, e.g. `build BMATS101 days=5`", [sender])
            return
        await build_and_publish(cmd["args"][0].upper(), int(cmd.get("days", 5)), sender, send)

    else:
        await send(f"I'm Radar Builder. Ask @{DATA_NAME} to `analyse <CODE>` first.", [sender] if sender else [])


if __name__ == "__main__":
    run_agent("radar_builder", handle)
