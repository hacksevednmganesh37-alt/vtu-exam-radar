# VTU Exam Radar

**VTU sites give you papers. We get you exam-ready.**

A student enters their subject, exam date, weak modules and study hours. Three AI agents talk to each
other in a **BAND** room: they read every past paper, find the questions VTU keeps repeating, write
model answers, check the web for scheme or timetable changes, and send back a day-by-day plan.

Built for *Diwali Festiverse: The Agent-to-Agent Hackathon (India Edition)*, Research — Data & Build track.

- Public dashboard (GitHub Pages): https://hacksevednmganesh37-alt.github.io/vtu-exam-radar/?subject=BMATS101
- Personal planner (web app): runs from this repo, see "Run it" below

## The problem
VTU circles and question-paper sites hand students a pile of PDFs. Students still have to guess which
questions matter, how to answer them, and how to fit everything into the few days before the exam,
especially when they are weak in some modules.

## How it works

```
Student fills the form (subject, exam date, weak modules, hours/day)
        │
        ▼
Radar Desk (web app) ──@Radar Data analyse BMATS101 days=5 req=…──▶ Radar Data
                                                                     │ reads every past paper (Gemini)
                                                                     │ checks the live web for updates
                                                                     ▼
                                                   DATA_READY ──▶ Radar Builder
                                                                     │ checks the data quality
             Radar Data ◀──────── NEED_MORE modules=3,5 ─────────────┤ (if a module is thin)
             finds more questions on the web ── DATA_READY round=2 ─▶│
                                                                     │ groups repeated questions,
                                                                     │ writes model answers,
                                                                     ▼ builds a plan around weak modules
Radar Desk ◀── PLAN_READY ── the student sees the plan + the live agent conversation
```

| Agent | Job |
|---|---|
| **Radar Desk** | The web app. Takes the student's request and posts it to the BAND room, then shows the agents' conversation live |
| **Radar Data** | Collects: extracts every question from past papers, reads the syllabus, pulls live info from the web, fills gaps on request |
| **Radar Builder** | Builds: checks the data, asks Radar Data for more when a module is thin, writes model answers and the day-by-day plan |

Agents only receive messages that @mention them, and they never auto-reply to each other, so there
are no message loops.

## What the student gets
- A day-by-day plan with time blocks; weak modules come first and the last day is revision
- The questions that repeat most across papers, each with a short model answer
- Live notes from the web (scheme changes, timetable news) with sources

## Tech
- **BAND**: agent-to-agent messaging (`band-sdk`, LangGraph adapter, REST API for the web app)
- **Gemini API** (`gemini-2.5-flash`): reading PDFs, grouping similar questions, model answers, plans, Google Search grounding
- **FastAPI**: the Radar Desk web app (`web/`)
- **GitHub Pages**: the public dashboard (`site/`)
- **GitHub Codespaces**: runs all three agents

## Run it

1. Open this repo in **GitHub Codespaces** (Code → Codespaces → Create).
2. Add these **Codespaces secrets** (GitHub → Settings → Codespaces → Secrets):
   `GEMINI_API_KEY`, `RADAR_DATA_ID`, `RADAR_DATA_KEY`, `RADAR_BUILDER_ID`, `RADAR_BUILDER_KEY`
   (optional: `RADAR_DESK_KEY` for a separate Desk agent).
3. Put PDFs in `papers/<SUBJECT_CODE>/` (see `papers/README.md`).
4. Start everything: `bash scripts/start_all.sh`. It prints the web app link.
5. Open the link, fill in the form and watch the agents work.

Test the pipeline without BAND: `uv run python scripts/run_local.py BMATS101 --no-push`

## Disclaimer
Predictions come from patterns in past papers. They are not official VTU information.
Students should still cover the full syllabus.
