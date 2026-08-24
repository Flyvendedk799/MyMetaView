#!/usr/bin/env python3
"""Reproducible runner for the preview engine corpus.

Walks the golden corpus, generates a card for each URL, **keeps the rendered
PNG and scores its pixels**, and writes everything into
``artifacts/baseline/<date>/``.

The scoring is the part that makes this a gate rather than a report. Before it,
a run could be green while every card shipped a headline at 1.2:1 contrast,
because every metric was read off the result dict rather than the artefact. Now
each card is measured — contrast, overflow, logo occupancy, palette match,
gradient-only — and ``--gate`` fails the build when a run is worse than the
stored baseline.

Usage:
    # nightly: run, score, record the trend, update the baseline
    python -m backend.scripts.preview_engine.run_corpus \\
        --output-dir artifacts/baseline --update-baseline

    # PR: run, score, fail if it regressed
    python -m backend.scripts.preview_engine.run_corpus \\
        --output-dir artifacts/pr --gate --max-urls 12
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("corpus_runner")


def _import_engine():
    """Import lazily so unit tests can run without the full backend stack."""
    from backend.services.preview_engine import (
        PreviewEngine,
        PreviewEngineConfig,
    )
    return PreviewEngine, PreviewEngineConfig


def _import_corpus():
    from backend.services.preview.corpus import (
        get_corpus,
        get_corpus_by_category,
        GoldenCorpusCategory,
        GoldenURL,
    )
    return get_corpus, get_corpus_by_category, GoldenCorpusCategory, GoldenURL


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the golden corpus")
    parser.add_argument("--output-dir", default="artifacts/baseline",
                        help="Where to write per-URL artifacts")
    parser.add_argument("--max-urls", type=int, default=0,
                        help="Optional cap; 0 = whole corpus")
    parser.add_argument("--include-shadow", action="store_true",
                        help="Include the rotating shadow corpus")
    parser.add_argument("--category", default=None,
                        help="Restrict to a single category")
    parser.add_argument("--quality-mode", default="balanced",
                        choices=["fast", "balanced", "ultra"])
    parser.add_argument("--workers", type=int, default=2,
                        help="Concurrent jobs (default 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just print the corpus and exit")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero when this run is worse than the baseline")
    parser.add_argument("--update-baseline", action="store_true",
                        help="Write this run's scores as the new baseline")
    parser.add_argument("--baseline", default="artifacts/corpus-baseline.json",
                        help="Path to the stored baseline scores")
    parser.add_argument("--trend", default="artifacts/corpus-trend.jsonl",
                        help="Append-only trend file, one line per run")
    parser.add_argument("--no-score", action="store_true",
                        help="Skip visual scoring (a smoke run that only checks it works)")
    return parser.parse_args(argv)


def _git_commit() -> str:
    """The commit under test, so a trend point can be traced to a change."""
    import subprocess

    for env_var in ("GITHUB_SHA", "RAILWAY_GIT_COMMIT_SHA", "COMMIT_SHA"):
        value = os.environ.get(env_var)
        if value:
            return value[:12]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip()[:12] if out.returncode == 0 else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def make_run_dir(base: str) -> Path:
    today = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
    path = Path(base) / today
    path.mkdir(parents=True, exist_ok=True)
    return path


def select_corpus(args: argparse.Namespace):
    get_corpus, get_corpus_by_category, GoldenCorpusCategory, GoldenURL = _import_corpus()
    if args.category:
        category = GoldenCorpusCategory(args.category)
        urls = get_corpus_by_category(category, include_shadow=args.include_shadow)
    else:
        urls = get_corpus(include_shadow=args.include_shadow)
    if args.max_urls and args.max_urls > 0:
        urls = urls[: args.max_urls]
    return urls


def run_single(
    *,
    entry,
    output_dir: Path,
    quality_mode: str,
) -> Dict[str, Any]:
    PreviewEngine, PreviewEngineConfig = _import_engine()
    started = time.time()
    record: Dict[str, Any] = {
        "url": entry.url,
        "category": entry.category.value,
        "expected_template_type": entry.expected_template_type,
        "expected_title_keywords": list(entry.expected_title_keywords),
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        config = PreviewEngineConfig(
            is_demo=True,
            enable_brand_extraction=True,
            enable_ai_reasoning=True,
            enable_composited_image=True,
            enable_cache=False,
        )
        engine = PreviewEngine(config)
        result = engine.generate(entry.url, cache_key_prefix=f"corpus:{quality_mode}:")
        record.update({
            "status": "ok",
            "title": result.title,
            "description": result.description,
            "template_type": (result.blueprint or {}).get("template_type"),
            "processing_time_ms": result.processing_time_ms,
            "trace_url": result.trace_url,
            "warnings": result.warnings or [],
            "quality_scores": result.quality_scores or {},
            "title_match": entry.matches_title(result.title or ""),
            "default_palette_used": _has_default_palette(result.blueprint or {}),
            "primary_image_url": result.composited_preview_image_url,
            "blueprint": result.blueprint or {},
            "rendered_layout": result.rendered_layout,
            # Which fallbacks fired. A run where half the cards took the
            # favicon path is a different run from one where none did, even if
            # both score the same on average.
            "degradations": result.degradations,
            "job_trace_id": result.job_id,
        })
        _save_card(result.composited_preview_image_url, output_dir, entry.url)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Corpus run failed for %s", entry.url)
        record.update({
            "status": "fail",
            "error": str(exc),
            "title_match": False,
        })

    record["elapsed_seconds"] = round(time.time() - started, 2)
    record["finished_at"] = datetime.utcnow().isoformat()

    (output_dir / f"{_safe_name(entry.url)}.json").write_text(json.dumps(record, indent=2))
    return record


def _save_card(image_url: Optional[str], output_dir: Path, source_url: str) -> Optional[Path]:
    """Keep the rendered PNG next to its record.

    Storing the artefact is what lets a human look at a regression the scores
    flagged, and what lets a re-score run without regenerating.
    """
    if not image_url:
        return None
    try:
        from backend.services.preview.net import fetch

        result = fetch(image_url, timeout=20.0)
        if not result.ok:
            return None
        cards = output_dir / "cards"
        cards.mkdir(parents=True, exist_ok=True)
        path = cards / (_safe_name(source_url) + ".png")
        path.write_bytes(result.content)
        return path
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not save card for %s: %s", source_url, exc)
        return None


def _safe_name(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").replace("/", "_")[:120]


def _has_default_palette(blueprint: Dict[str, Any]) -> bool:
    """Heuristic for "default" palette = the engine's hard-coded blue."""
    primary = (blueprint.get("primary_color") or "").lower()
    return primary in {"#2563eb", "#3b82f6", "#1e40af"}


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {}

    total = len(records)
    successes = [r for r in records if r.get("status") == "ok"]
    fails = [r for r in records if r.get("status") != "ok"]

    title_matches = sum(1 for r in successes if r.get("title_match"))
    default_palette_count = sum(1 for r in successes if r.get("default_palette_used"))

    durations_ms = [r.get("processing_time_ms") for r in successes
                    if isinstance(r.get("processing_time_ms"), (int, float))]
    durations_ms.sort()

    def _percentile(values: List[float], pct: float) -> Optional[float]:
        if not values:
            return None
        k = max(0, min(len(values) - 1, int(round((pct / 100) * (len(values) - 1)))))
        return values[k]

    aggregate_record: Dict[str, Any] = {
        "total": total,
        "successful": len(successes),
        "failed": len(fails),
        "success_rate": round(len(successes) / total, 3),
        "title_fidelity": round(title_matches / max(1, len(successes)), 3),
        "default_palette_incidence": round(default_palette_count / max(1, len(successes)), 3),
        "p50_ms": _percentile(durations_ms, 50),
        "p95_ms": _percentile(durations_ms, 95),
        "fails_by_url": [r.get("url") for r in fails],
    }
    return aggregate_record


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    urls = select_corpus(args)
    if args.dry_run:
        for entry in urls:
            print(f"{entry.category.value}: {entry.url}")
        print(f"total={len(urls)}")
        return 0

    run_dir = make_run_dir(args.output_dir)
    logger.info("Writing artifacts to %s", run_dir)

    records: List[Dict[str, Any]] = []
    if args.workers <= 1:
        for entry in urls:
            records.append(run_single(entry=entry, output_dir=run_dir,
                                       quality_mode=args.quality_mode))
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {
                ex.submit(run_single, entry=entry, output_dir=run_dir,
                          quality_mode=args.quality_mode): entry
                for entry in urls
            }
            for fut in as_completed(futures):
                records.append(fut.result())

    summary = aggregate(records)
    (run_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    logger.info("Run complete: %s", summary)

    if args.no_score:
        logger.info("Visual scoring skipped (--no-score)")
        return 0

    # ---- score the cards, not the dicts -------------------------------
    from backend.services.preview.corpus.scoring import (
        append_trend,
        compare_runs,
        load_baseline,
        save_baseline,
        score_run,
    )

    scores = score_run(
        records,
        commit=_git_commit(),
        ran_at=datetime.utcnow().isoformat(),
        fetch_image=lambda url: _read_local_card(run_dir, records, url),
    ).to_dict()
    (run_dir / "SCORES.json").write_text(json.dumps(scores, indent=2))
    logger.info(
        "Visual scores: mean=%.3f contrast=%.2f pass_rate=%.2f gradient_only=%d unreadable=%d",
        scores["mean_overall"], scores["mean_title_contrast"], scores["pass_rate"],
        scores["gradient_only_count"], scores["unreadable_count"],
    )
    if scores["degradation_counts"]:
        logger.info("Degradations across the run: %s", scores["degradation_counts"])

    append_trend(Path(args.trend), scores)

    baseline_path = Path(args.baseline)
    comparison = compare_runs(scores, load_baseline(baseline_path))
    print(comparison.report())
    (run_dir / "COMPARISON.json").write_text(json.dumps({
        "regressed": comparison.regressed,
        "reasons": comparison.reasons,
        "improvements": comparison.improvements,
        "deltas": comparison.deltas,
        "per_url_regressions": comparison.per_url_regressions,
    }, indent=2))

    # Update the baseline only when asked and only when the run is not a
    # regression — otherwise a bad night silently becomes the new normal and
    # the gate can never fire again.
    if args.update_baseline and not comparison.regressed:
        save_baseline(baseline_path, scores)
        logger.info("Baseline updated: %s", baseline_path)
    elif args.update_baseline:
        logger.warning("Baseline NOT updated — this run regressed")

    if args.gate and comparison.regressed:
        logger.error("Corpus gate failed")
        return 1
    return 0


def _read_local_card(run_dir: Path, records: List[Dict[str, Any]], image_url: str) -> Optional[bytes]:
    """Score the PNG we already saved rather than downloading it again.

    Falls back to a guarded fetch when the local copy is missing, so a run that
    failed to save a card is still scored rather than silently counted as a
    render failure.
    """
    for record in records:
        if record.get("primary_image_url") == image_url:
            path = run_dir / "cards" / (_safe_name(record.get("url", "")) + ".png")
            if path.exists():
                return path.read_bytes()
            break
    try:
        from backend.services.preview.net import fetch

        result = fetch(image_url, timeout=15.0)
        return result.content if result.ok else None
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
