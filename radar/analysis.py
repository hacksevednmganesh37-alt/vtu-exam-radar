"""Core work for both agents: read papers, find gaps, build the report, publish it.

Folder layout:
  papers/<SUBJECT_CODE>/*.pdf          past question papers (any names)
  papers/<SUBJECT_CODE>/syllabus.pdf   optional syllabus
  work/<SUBJECT_CODE>/                 cache + agent conversation log
  site/data/<SUBJECT_CODE>.json        what the dashboard shows
"""
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from radar import gemini

ROOT = Path(__file__).resolve().parent.parent
PAPERS = ROOT / "papers"
WORK = ROOT / "work"
SITE_DATA = ROOT / "site" / "data"

MODULES = [1, 2, 3, 4, 5]          # VTU papers have 5 modules
MIN_QUESTIONS_PER_MODULE = 4       # fewer than this = "gap", Builder asks for more


# ---------- small helpers ----------

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def work_dir(code: str) -> Path:
    d = WORK / code
    (d / "papers").mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def log_message(code: str, sender: str, to: str, message: str) -> None:
    """Keep the agent-to-agent conversation so the dashboard can show it."""
    path = work_dir(code) / "agent_log.json"
    log = read_json(path, [])
    log.append({"time": now(), "from": sender, "to": to, "message": message})
    write_json(path, log)


# ---------- DATA AGENT work ----------

PAPER_PROMPT = """You are reading a VTU (Visvesvaraya Technological University) exam question paper.
Extract EVERY question and sub-question.

VTU papers are split into Module-1 ... Module-5 (usually Q1/Q2 = Module 1, Q3/Q4 = Module 2, and so on).
Return JSON:
{
  "subject_name": "full subject name if printed, else empty",
  "exam": "exam session as printed, e.g. 'Dec 2023/Jan 2024', else the best guess",
  "questions": [
    {"number": "1a", "module": 1, "marks": 6, "text": "the question text, cleaned up"}
  ]
}
Rules: module must be an integer 1-5. marks must be a number (0 if not shown). Keep formulas readable in plain text."""

SYLLABUS_PROMPT = """This is a VTU syllabus. Return JSON:
{"subject_name": "...", "modules": [{"number": 1, "title": "short title", "topics": ["topic", "..."]}]}
Include all 5 modules."""


def paper_files(code: str) -> list[Path]:
    folder = PAPERS / code
    if not folder.exists():
        raise FileNotFoundError(
            f"No folder papers/{code}/ - upload the question paper PDFs there first."
        )
    return sorted(p for p in folder.glob("*.pdf") if "syllabus" not in p.name.lower())


def read_syllabus(code: str) -> dict | None:
    cache = work_dir(code) / "syllabus.json"
    if cache.exists():
        return read_json(cache, None)
    pdf = PAPERS / code / "syllabus.pdf"
    if not pdf.exists():
        return None
    data = gemini.ask_json(SYLLABUS_PROMPT, files=[gemini.upload(str(pdf))])
    write_json(cache, data)
    return data


def read_paper(code: str, pdf: Path) -> dict:
    """Extract questions from one paper (cached, so re-runs are free)."""
    cache = work_dir(code) / "papers" / f"{pdf.stem}.json"
    if cache.exists():
        return read_json(cache, {})
    data = gemini.ask_json(PAPER_PROMPT, files=[gemini.upload(str(pdf))])
    data["file"] = pdf.name
    write_json(cache, data)
    return data


def live_notes(code: str, subject_name: str) -> dict:
    """Live web check: latest scheme, exam timetable news, syllabus changes."""
    prompt = f"""Search the web for the latest official information about the VTU subject
{code} ({subject_name}). Look for: current scheme/syllabus version, any recent syllabus changes,
and upcoming VTU exam timetable news. Prefer vtu.ac.in.
Return JSON: {{"notes": ["short fact 1", "short fact 2", "..."]}} (3-5 notes, each one sentence)."""
    data, sources = gemini.ask_web(prompt)
    notes = (data or {}).get("notes", []) if isinstance(data, dict) else []
    return {"notes": notes, "sources": sources[:5], "checked_at": now()}


def collect(code: str) -> dict:
    """Data Agent main job: read all papers + syllabus + live web notes into one dataset."""
    papers = [read_paper(code, pdf) for pdf in paper_files(code)]
    if not papers:
        raise FileNotFoundError(f"papers/{code}/ has no PDF question papers yet.")
    syllabus = read_syllabus(code)

    subject_name = (syllabus or {}).get("subject_name") or next(
        (p.get("subject_name") for p in papers if p.get("subject_name")), code
    )

    questions = []
    for p in papers:
        for i, q in enumerate(p.get("questions", [])):
            module = q.get("module")
            if module not in MODULES:
                continue
            questions.append({
                "id": f"{Path(p['file']).stem}-{i}",
                "exam": p.get("exam", p["file"]),
                "module": module,
                "marks": float(q.get("marks") or 0),
                "text": q.get("text", "").strip(),
                "source": "past paper",
            })

    dataset = {
        "code": code,
        "subject_name": subject_name,
        "papers": [p.get("exam", p["file"]) for p in papers],
        "syllabus": syllabus,
        "questions": questions,
        "web_questions": [],
        "live": live_notes(code, subject_name),
        "collected_at": now(),
    }
    write_json(work_dir(code) / "dataset.json", dataset)
    return dataset


def load_dataset(code: str) -> dict:
    path = work_dir(code) / "dataset.json"
    if not path.exists():
        raise FileNotFoundError(f"No dataset for {code} yet - ask Radar Data to analyse it first.")
    return read_json(path, {})


def enrich(code: str, modules: list[int]) -> dict:
    """Data Agent extra job: Builder found thin modules, so search the web for more."""
    dataset = load_dataset(code)
    syllabus_modules = {m["number"]: m for m in (dataset.get("syllabus") or {}).get("modules", [])}
    for module in modules:
        topics = ", ".join(syllabus_modules.get(module, {}).get("topics", [])) or "the module topics"
        prompt = f"""Search the web for frequently asked VTU exam questions for subject
{dataset['code']} ({dataset['subject_name']}), Module {module} ({topics}).
Use question banks, model papers and VTU resources.
Return JSON: {{"questions": [{{"text": "question", "marks": 8}}]}} with 5-8 questions."""
        data, sources = gemini.ask_web(prompt)
        found = (data or {}).get("questions", []) if isinstance(data, dict) else []
        for i, q in enumerate(found):
            dataset["web_questions"].append({
                "id": f"web-m{module}-{i}",
                "exam": "web search",
                "module": module,
                "marks": float(q.get("marks") or 0),
                "text": str(q.get("text", "")).strip(),
                "source": "web",
                "links": sources[:3],
            })
    write_json(work_dir(code) / "dataset.json", dataset)
    return dataset


# ---------- BUILDER AGENT work ----------

def find_gaps(dataset: dict) -> list[int]:
    """Modules with too few past-paper questions to judge importance."""
    counts = defaultdict(int)
    for q in dataset["questions"]:
        counts[q["module"]] += 1
    return [m for m in MODULES if counts[m] < MIN_QUESTIONS_PER_MODULE]


CLUSTER_PROMPT = """These are questions from several VTU exam papers for one subject.
Group questions that ask essentially the same thing (same concept/derivation/problem type),
even if the wording or numbers differ.
Return JSON: {{"groups": [{{"title": "short clear version of the question", "ids": ["id1", "id2"]}}]}}
Every id must appear in exactly one group. Questions:
{questions}"""

PLAN_PROMPT = """Make a {days}-day VTU exam study plan for {subject}.
Module weightage from past papers (share of total marks): {weights}
Most repeated questions: {repeated}
Rules: highest-weight modules and most-repeated questions first; last day = revision + solving
the top repeated questions. Keep tasks short and concrete.
Return JSON: {{"plan": [{{"day": 1, "focus": "Module 2 - title", "tasks": ["task", "task"]}}]}}"""


def module_stats(dataset: dict) -> list[dict]:
    titles = {m["number"]: m.get("title", "") for m in (dataset.get("syllabus") or {}).get("modules", [])}
    marks = defaultdict(float)
    count = defaultdict(int)
    for q in dataset["questions"]:
        marks[q["module"]] += q["marks"]
        count[q["module"]] += 1
    total = sum(marks.values()) or 1
    return [{
        "number": m,
        "title": titles.get(m, ""),
        "question_count": count[m],
        "total_marks": round(marks[m], 1),
        "share": round(marks[m] / total, 3),
    } for m in MODULES]


def repeated_questions(dataset: dict) -> list[dict]:
    qs = dataset["questions"]
    by_id = {q["id"]: q for q in qs}
    listing = "\n".join(f"[{q['id']}] (Module {q['module']}) {q['text']}" for q in qs)
    groups = gemini.ask_json(CLUSTER_PROMPT.format(questions=listing)).get("groups", [])

    result = []
    for g in groups:
        members = [by_id[i] for i in g.get("ids", []) if i in by_id]
        if not members:
            continue
        exams = sorted({m["exam"] for m in members})
        result.append({
            "question": g.get("title") or members[0]["text"],
            "module": members[0]["module"],
            "times": len(exams),
            "exams": exams,
            "avg_marks": round(sum(m["marks"] for m in members) / len(members), 1),
        })
    result.sort(key=lambda r: (-r["times"], -r["avg_marks"]))
    return result


def build_report(code: str, days: int) -> dict:
    dataset = load_dataset(code)
    modules = module_stats(dataset)
    repeated = repeated_questions(dataset)
    top = repeated[:12]

    weights = ", ".join(f"Module {m['number']}: {m['share']:.0%}" for m in modules)
    rep_text = "; ".join(f"{r['question']} (asked {r['times']}x, Module {r['module']})" for r in top)
    plan = gemini.ask_json(PLAN_PROMPT.format(
        days=days, subject=dataset["subject_name"], weights=weights, repeated=rep_text
    )).get("plan", [])

    report = {
        "code": code,
        "subject_name": dataset["subject_name"],
        "generated_at": now(),
        "days": days,
        "papers": dataset["papers"],
        "modules": modules,
        "repeated_questions": top,
        "web_questions": dataset.get("web_questions", []),
        "study_plan": plan,
        "live": dataset.get("live", {}),
        "agent_log": read_json(work_dir(code) / "agent_log.json", []),
        "sample": False,
    }
    return report


def publish(report: dict, push: bool = True) -> None:
    """Write the dashboard data. With push=True, git push so Vercel redeploys."""
    code = report["code"]
    write_json(SITE_DATA / f"{code}.json", report)

    index_path = SITE_DATA / "subjects.json"
    index = [s for s in read_json(index_path, []) if s["code"] != code]
    index.insert(0, {"code": code, "name": report["subject_name"], "updated": report["generated_at"]})
    write_json(index_path, index)

    if push:
        def git(*args):
            subprocess.run(["git", *args], cwd=ROOT, check=True)
        git("add", "site/data")
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
        if result.returncode != 0:
            git("commit", "-m", f"Radar Builder: update dashboard for {code}")
            git("push")
