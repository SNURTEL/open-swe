"""Run the reviewer eval.

Usage:
    uv run python -m evals.reviewer.run_eval \\
        --dataset-name openswe-reviewer-v1 \\
        --experiment-prefix openswe-reviewer-baseline \\
        --max-concurrency 5

Note: Running this eval requires an evaluation framework such as LangSmith's
``aevaluate``. Install the required dependencies and update this module to
use the desired harness.
"""

from __future__ import annotations

import argparse
import logging

from langgraph_sdk import get_client

from evals.reviewer.target import LANGGRAPH_URL, drain_thread_ids

logger = logging.getLogger(__name__)


async def _cleanup_threads(thread_ids) -> None:
    """Delete LangGraph threads created during the eval."""
    sdk = get_client(url=LANGGRAPH_URL)
    for tid in thread_ids:
        try:
            await sdk.threads.delete(tid)
        except Exception as exc:
            logger.warning("Failed to delete thread %s: %s", tid, exc)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-name", default="openswe-reviewer-v1")
    ap.add_argument("--experiment-prefix", default="openswe-reviewer-baseline")
    ap.add_argument("--max-concurrency", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None, help="Run only the first N examples.")
    ap.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip deleting LangGraph threads after the experiment finishes.",
    )
    ap.parse_args()

    raise NotImplementedError(
        "Running evals requires an evaluation framework. "
        "Integrate an evaluation harness (e.g. a local runner or alternative service) "
        "and re-implement this function."
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
