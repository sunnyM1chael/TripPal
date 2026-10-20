"""Bounded extractive task summaries; never promoted to the user's permanent profile."""
import json


def extend_summary(previous: str, turns: list[dict]) -> str:
    try:
        items = json.loads(previous or "[]")
        if not isinstance(items, list):
            items = []
    except (ValueError, TypeError):
        items = []
    # Keep original user language with explicit provenance rather than fabricate facts via an LLM.
    items.extend({"user_request": turn["prompt"][:300], "past_reply_excerpt": turn["output"][:160]} for turn in turns)
    return json.dumps(items[-10:], ensure_ascii=False)
