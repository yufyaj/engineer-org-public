#!/usr/bin/env python3
"""Report only model metadata from this consultation's Claude transcript."""
import argparse
import json
import os
from pathlib import Path
import re
import uuid


def check(config, session, agent):
    if str(uuid.UUID(session)) != session:
        raise ValueError("Invalid session ID")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", agent):
        raise ValueError("Invalid agent ID")
    base = Path(config).resolve() / "projects"
    matches = list(base.glob("*/" + session + "/subagents/agent-" + agent + ".jsonl"))
    if len(matches) != 1:
        raise ValueError("Consultation transcript missing or ambiguous")
    path = matches[0]
    if any(part.is_symlink() for part in [path, *path.parents]) or path.stat().st_size > 10_000_000:
        raise ValueError("Unsupported transcript path or size")
    models = set()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("type") != "assistant":
                continue
            model = event.get("message", {}).get("model")
            if not isinstance(model, str) or not re.fullmatch(r"claude-(?:fable|opus|sonnet|haiku|mythos)-[0-9][a-z0-9.-]{0,100}", model):
                raise ValueError("Missing or invalid model metadata")
            models.add(model)
    return {"verified_fable": bool(models) and all(m.startswith("claude-fable-") for m in models),
            "models": sorted(models), "session": session, "agent": agent}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--agent", required=True)
    args = parser.parse_args()
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    try:
        result = check(config, args.session, args.agent)
    except (ValueError, OSError, TypeError, AttributeError):
        # Never echo a transcript, malformed line, environment, or exception text.
        result = {"verified_fable": False, "status": "unverified"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["verified_fable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
