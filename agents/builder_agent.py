"""RADAR BUILDER - checks the data, asks Radar Data for more if needed, builds the (personal) plan.

Messages it understands:
  DATA_READY <CODE> days=N round=1|2 req=<id> requested_by=<name>   (from Radar Data)
  build <CODE> [days=N]                                              (from a student, skips the gap check)

With req=<id> (a request from the web app) it builds a PERSONAL plan and tells Radar Desk.
Without it, it publishes the general subject dashboard.
"""
import asyncio
import os

from radar import analysis
from radar.band_helper import BUILDER_NAME, DATA_NAME, DESK_NAME, is_agent, parse_command, run_agent

SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
PUSH = os.environ.get("PUBLISH_PUSH", "1") == "1"   # set to 0 to skip git push while testing


async def build_and_publish(code: str, days: int, requester: str, req: str, send) -> None:
    request = analysis.load_request(req) if req else None
    if request:
        days = analysis.days_until(request.get("exam_date"))
        weak = request.get("weak_modules") or []
        analysis.log_message(code, BUILDER_NAME, DESK_NAME,
                             f"Building a {days}-day plan, {request.get('hours', 4)}h/day"
                             + (f", weak modules {', '.join(map(str, weak))} first" if weak else "")
                             + ", with model answers.", req)
    else:
        analysis.log_message(code, BUILDER_NAME, requester or "students", "Building the subject dashboard and publishing it.")

    report = await asyncio.to_thread(analysis.build_report, code, days, request)

    if request:
        request = analysis.load_request(req) or request
        request["plan"] = report
        request["status"] = "done"
        analysis.save_request(request)
        analysis.log_message(code, BUILDER_NAME, DESK_NAME, "Plan ready. Sending it to the student.", req)
        await send(f"@{DESK_NAME} PLAN_READY {code} req={req}", [DESK_NAME])
        return

    await asyncio.to_thread(analysis.publish, report, PUSH)
    top = report["repeated_questions"][:3]
    top_text = "\n".join(f"- {r['question']} (asked {r['times']}x)" for r in top) or "- (no repeats found)"
    link = f"{SITE_URL}/?subject={code}" if SITE_URL else f"site/data/{code}.json"
    if requester and not is_agent(requester):
        await send(
            f"Dashboard ready for {report['subject_name']} ({code})!\n"
            f"Top repeated questions:\n{top_text}\nFull {days}-day plan: {link}",
            [requester],
        )


async def handle(sender: str, text: str, send) -> None:
    cmd = parse_command(text)
    action = cmd["action"]
    req = cmd.get("req", "")
    human = sender and not is_agent(sender)
    if analysis.is_stale(req):
        return  # old message re-delivered after a restart: skip it

    if action == "DATA_READY":
        if not cmd["args"]:
            return
        code = cmd["args"][0].upper()
        days = int(cmd.get("days", 5) or 5)
        round_no = int(cmd.get("round", 1) or 1)
        requester = cmd["requested_by"]

        dataset = analysis.load_dataset(code)
        gaps = analysis.find_gaps(dataset)
        if gaps and round_no == 1:
            # Agent-to-agent step: Builder can't rank thin modules, so it asks Data for more.
            gap_text = ",".join(map(str, gaps))
            analysis.log_message(code, BUILDER_NAME, DATA_NAME,
                                 f"Module(s) {gap_text} have too few questions to rank. Please find more.", req)
            await send(
                f"@{DATA_NAME} NEED_MORE {code} modules={gap_text} days={days} round=1 req={req} requested_by={requester}",
                [DATA_NAME],
            )
            return
        await build_and_publish(code, days, requester, req, send)

    elif action == "BUILD" and human:
        if not cmd["args"]:
            await send("Tell me a subject code, e.g. `build BMATS101 days=5`", [sender])
            return
        await build_and_publish(cmd["args"][0].upper(), int(cmd.get("days", 5)), sender, "", send)

    elif human:
        await send(f"I'm Radar Builder. Ask @{DATA_NAME} to `analyse <CODE>` first.", [sender])
    # non-command messages from agents are ignored on purpose (no reply loops)


if __name__ == "__main__":
    run_agent("radar_builder", handle)
