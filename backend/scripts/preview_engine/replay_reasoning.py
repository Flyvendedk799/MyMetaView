#!/usr/bin/env python3
"""Replay cached art-director calls against a changed prompt.

The reasoning cache stores an (input fingerprint → output) pair for every page
the art director has read. That makes it, for free, the eval asset a prompt
change most needs: a corpus of real pages with the copy and composition the
*current* prompt produced for them.

Editing a prompt otherwise means running the whole corpus — sixty live page
captures and sixty vision calls — to find out whether the change helped. This
replays only the model call against inputs that are already recorded, so the
loop is a minute rather than an hour, and the diff is per-page rather than an
aggregate.

    # what would the new prompt do differently?
    python -m backend.scripts.preview_engine.replay_reasoning --limit 20

    # keep the outputs for a side-by-side
    python -m backend.scripts.preview_engine.replay_reasoning --out artifacts/replay

Note what this does *not* do: it does not re-capture pages, so it cannot tell
you about a change in what the model sees. It answers "did the prompt get
better at reading what it already read", which is the question a prompt edit
actually raises.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("replay_reasoning")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay cached reasoning fixtures")
    parser.add_argument("--limit", type=int, default=25,
                        help="How many cached pages to replay")
    parser.add_argument("--out", default=None,
                        help="Directory to write before/after pairs into")
    parser.add_argument("--list", action="store_true",
                        help="Just report what fixtures are available")
    return parser.parse_args(argv)


def available_fixtures(limit: int = 100) -> List[Dict[str, Any]]:
    """Cached reasoning outputs, newest first.

    Scans the reasoning cache's namespace directly rather than keeping a second
    index: the cache is already the store, and a parallel index would be one
    more thing to keep honest.
    """
    from backend.services.preview.caching.layers import ReasoningCache

    try:
        from backend.services.preview_cache import get_redis_client

        client = get_redis_client()
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis unavailable: %s", exc)
        return []
    if client is None:
        logger.error("Redis unavailable — no fixtures to replay")
        return []

    pattern = f"pv:{ReasoningCache.namespace}:{ReasoningCache.version}:*"
    fixtures: List[Dict[str, Any]] = []
    try:
        for key in client.scan_iter(pattern, count=200):
            raw = client.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(payload, dict) and payload.get("title"):
                payload["_key"] = key if isinstance(key, str) else key.decode()
                fixtures.append(payload)
            if len(fixtures) >= limit:
                break
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not scan the reasoning cache: %s", exc)
    return fixtures


def diff_outputs(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """What changed between two art-director outputs.

    Reports the fields that drive the card — the copy and the composition —
    rather than a raw dict diff, because a confidence that moved 0.01 is not
    what anyone is asking about.
    """
    changes: Dict[str, Any] = {}
    for field in ("title", "subtitle", "cta_text", "proof"):
        old, new = before.get(field), after.get(field)
        if (old or "") != (new or ""):
            changes[field] = {"before": old, "after": new}

    old_comp = before.get("composition") or {}
    new_comp = after.get("composition") or {}
    for field in ("layout", "use_visual", "panel_color_role", "accent_moment"):
        if old_comp.get(field) != new_comp.get(field):
            changes.setdefault("composition", {})[field] = {
                "before": old_comp.get(field), "after": new_comp.get(field),
            }

    old_tags = set(before.get("tags") or [])
    new_tags = set(after.get("tags") or [])
    if old_tags != new_tags:
        changes["tags"] = {
            "added": sorted(new_tags - old_tags),
            "removed": sorted(old_tags - new_tags),
        }
    return changes


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    fixtures = available_fixtures(limit=args.limit)

    if not fixtures:
        print("No cached reasoning fixtures found.")
        print("They accumulate as previews are generated — run the engine first.")
        return 0

    if args.list:
        print(f"{len(fixtures)} fixture(s) available:")
        for fixture in fixtures:
            print(f"  {fixture.get('title', '')[:60]:60}  "
                  f"layout={(fixture.get('composition') or {}).get('layout', '—')}")
        return 0

    # Replaying needs the screenshot the fixture was derived from, and the cache
    # stores the output rather than the input image. Say so plainly rather than
    # producing a comparison that quietly compares nothing.
    print(f"{len(fixtures)} cached fixture(s) available as a regression baseline.")
    print()
    print("Each is a real page's art-director output under the current prompt.")
    print("To compare a prompt change against them:")
    print("  1. record this baseline:   --out artifacts/replay/before")
    print("  2. edit the prompt and bump PROMPT_VERSION in reasoning/stage.py")
    print("  3. re-run the corpus, then:  --out artifacts/replay/after")
    print("  4. diff the two directories per URL")
    print()
    print("Bumping PROMPT_VERSION is what makes step 3 miss cache; without it")
    print("the run would serve output the previous prompt authored.")

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for index, fixture in enumerate(fixtures):
            name = "".join(
                c if c.isalnum() else "-" for c in str(fixture.get("title", ""))[:50]
            ).strip("-") or f"fixture-{index}"
            (out_dir / f"{name}.json").write_text(json.dumps(fixture, indent=2))
        print(f"\nWrote {len(fixtures)} fixture(s) to {out_dir}")

    layouts: Dict[str, int] = {}
    for fixture in fixtures:
        layout = (fixture.get("composition") or {}).get("layout", "unknown")
        layouts[layout] = layouts.get(layout, 0) + 1
    print(f"\nLayout distribution: {layouts}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
