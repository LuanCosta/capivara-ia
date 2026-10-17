"""Offline report for saved Fly logs; no API keys, network or database access.

python tools/ai_usage_report.py fly-ai.log
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai_usage import UsageMeter


def report(lines):
    counter = UsageMeter()
    seen = set()
    timestamps = []
    for line in lines:
        if "AI_USAGE " not in line:
            continue
        try:
            event = json.JSONDecoder().raw_decode(line.split("AI_USAGE ", 1)[1])[0]
            event_id = event["event_id"]
            if event.get("event") != "ai_usage" or event.get("schema_version") != 1 or event_id in seen:
                continue
            counter.record(event)
            seen.add(event_id)
            timestamps.append(event["at"])
        except (ValueError, KeyError, TypeError):
            continue
    result = counter.snapshot()
    result.update(scope="captured_log_events_only", since=min(timestamps) if timestamps else None,
                  until=max(timestamps) if timestamps else None, unique_events=len(seen))
    result.pop("process_instance", None)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path)
    args = parser.parse_args()
    raw = args.logfile.read_bytes()
    text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig", errors="replace")
    result = report(text.splitlines())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["unique_events"]:
        raise SystemExit("Nenhum evento AI_USAGE encontrado. Isso não comprova gasto zero.")
