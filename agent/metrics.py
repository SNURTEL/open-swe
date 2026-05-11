"""Prometheus-compatible runtime metrics."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SDD_RUNS_TOTAL = Counter(
    "open_swe_sdd_runs_total",
    "Total number of SDD run transitions",
    ["source", "status"],
)

SDD_CI_FIX_ROUNDS_TOTAL = Counter(
    "open_swe_ci_fix_rounds_total",
    "Total number of CI autofix rounds triggered",
    ["repo_owner", "repo_name"],
)

SDD_RUN_DURATION_SECONDS = Histogram(
    "open_swe_sdd_run_duration_seconds",
    "Observed SDD run duration in seconds",
    ["source"],
)


def observe_sdd_run_transition(source: str, status: str) -> None:
    SDD_RUNS_TOTAL.labels(source=source, status=status).inc()


def observe_ci_fix_round(repo_owner: str, repo_name: str) -> None:
    SDD_CI_FIX_ROUNDS_TOTAL.labels(repo_owner=repo_owner, repo_name=repo_name).inc()


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
