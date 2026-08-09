"""RQ worker supervisor for background jobs.

Historically this module ran a single RQ worker on the `preview_generation`
queue, which meant one preview at a time and — worse — a long bulk run could
block every interactive generation behind it.

It now supervises a small POOL of worker processes:

- INTERACTIVE workers drain only `preview_generation` (single-URL previews and
  regenerations). Count = PREVIEW_WORKER_COUNT (default 2). Bulk never blocks
  these.
- A BULK worker drains `bulk_generation` first, then falls back to helping with
  interactive work when no bulk is queued. Count = BULK_WORKER_COUNT (default 1).

Each Chromium-backed job uses ~300-500MB RAM, so keep the total modest on shared
hosts. Tune with env vars PREVIEW_WORKER_COUNT / BULK_WORKER_COUNT.

The container command stays `python -m backend.queue.worker`; the fan-out happens
here so no deploy/infra config has to change.
"""
import logging
import os
import signal
import time
from multiprocessing import Process

from rq import Worker, Queue
from backend.queue.queue_connection import get_rq_redis_connection
from backend.utils.logger import setup_logging

INTERACTIVE_QUEUE = "preview_generation"
BULK_QUEUE = "bulk_generation"


def _run_worker(queue_names, name):
    """Entry point for a single worker process: drain the given queues forever."""
    setup_logging(level="INFO")
    logger = logging.getLogger(f"rq.worker.{name}")
    redis_conn = get_rq_redis_connection()
    queues = [Queue(q, connection=redis_conn) for q in queue_names]
    worker = Worker(queues, connection=redis_conn, name=f"{name}-{os.getpid()}")
    logger.info("worker '%s' (pid=%s) listening on %s", name, os.getpid(), queue_names)
    worker.work()


def _int_env(key, default):
    try:
        return max(0, int(os.environ.get(key, str(default))))
    except (TypeError, ValueError):
        return default


def _build_specs():
    """Return the list of (queue_names, name) worker specs to run."""
    n_interactive = _int_env("PREVIEW_WORKER_COUNT", 2)
    n_bulk = _int_env("BULK_WORKER_COUNT", 1)
    if n_interactive + n_bulk == 0:
        n_interactive = 1  # never boot with zero workers

    specs = []
    for i in range(n_interactive):
        specs.append(([INTERACTIVE_QUEUE], f"interactive{i + 1}"))
    for i in range(n_bulk):
        # Bulk first, then help with interactive work when no bulk is queued.
        specs.append(([BULK_QUEUE, INTERACTIVE_QUEUE], f"bulk{i + 1}"))
    return specs


def main():
    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)

    specs = _build_specs()
    logger.info("Starting worker pool: %d process(es) -> %s",
                len(specs), [s[1] for s in specs])

    procs = {}

    def spawn(spec):
        queue_names, name = spec
        p = Process(target=_run_worker, args=(queue_names, name), name=name)
        p.start()
        procs[p.pid] = (p, spec)
        logger.info("spawned worker '%s' pid=%s queues=%s", name, p.pid, queue_names)

    for spec in specs:
        spawn(spec)

    shutting_down = {"flag": False}

    def handle_signal(signum, _frame):
        shutting_down["flag"] = True
        logger.info("received signal %s — terminating worker pool", signum)
        for p, _spec in list(procs.values()):
            if p.is_alive():
                p.terminate()  # RQ handles SIGTERM as a warm shutdown

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Supervise: restart any worker that dies, unless we're shutting down.
    while not shutting_down["flag"]:
        time.sleep(5)
        for pid, (p, spec) in list(procs.items()):
            if not p.is_alive():
                del procs[pid]
                if shutting_down["flag"]:
                    continue
                logger.warning("worker '%s' (pid=%s) exited code=%s — restarting",
                               spec[1], pid, p.exitcode)
                time.sleep(1)
                spawn(spec)

    for p, _spec in list(procs.values()):
        p.join(timeout=30)
    logger.info("worker supervisor exited cleanly")


if __name__ == "__main__":
    main()
