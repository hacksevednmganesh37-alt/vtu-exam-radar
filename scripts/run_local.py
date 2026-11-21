"""Test the whole pipeline WITHOUT BAND (useful for checking Gemini + papers work).

  uv run python scripts/run_local.py BMATS101 --days 5 --no-push
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import analysis  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("code")
    p.add_argument("--days", type=int, default=5)
    p.add_argument("--no-push", action="store_true", help="don't git push")
    a = p.parse_args()
    code = a.code.upper()

    print(f"[Data] reading papers for {code} ...")
    ds = analysis.collect(code)
    print(f"[Data] {len(ds['papers'])} papers, {len(ds['questions'])} questions")
    analysis.log_message(code, "Radar Data", "Radar Builder", f"Collected {len(ds['questions'])} questions.")

    gaps = analysis.find_gaps(ds)
    if gaps:
        print(f"[Builder] thin modules {gaps} -> asking Data for more")
        analysis.log_message(code, "Radar Builder", "Radar Data", f"Need more on modules {gaps}.")
        ds = analysis.enrich(code, gaps)
        analysis.log_message(code, "Radar Data", "Radar Builder", f"Added {len(ds['web_questions'])} web questions.")

    print("[Builder] building report ...")
    report = analysis.build_report(code, a.days)
    analysis.publish(report, push=not a.no_push)
    print(f"[Builder] done -> site/data/{code}.json")


if __name__ == "__main__":
    main()
