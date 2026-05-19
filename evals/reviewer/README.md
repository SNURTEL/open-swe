# Reviewer Eval

Offline eval for the Open SWE Reviewer graph against the 50 PRs from
[withmartian/code-review-benchmark](https://github.com/withmartian/code-review-benchmark).

## Layout

```
evals/reviewer/
├── build_dataset.py      # martian JSON → local dataset (resolves SHAs via gh)
├── run_eval.py           # eval runner (requires an evaluation framework)
├── judge.py              # LLM judge: per-example precision/recall/F1
├── target.py             # async target function that calls the reviewer graph
└── golden_comments/      # JSON files with expected review comments
```

## Setup

- The reviewer graph must be running (e.g. via `langgraph dev`).

## Usage

**1. Build the dataset (dry run)**

```bash
uv run python -m evals.reviewer.build_dataset --dry-run --limit 5
```

**2. Implement an eval runner**

`run_eval.py` raises `NotImplementedError` by default. Integrate an evaluation
harness (e.g. a custom runner or alternative service) and update the module to
invoke `review_pr` and score results using the `judge_match` / `aggregate_pr`
evaluators from `judge.py`.

## Metrics

The judge produces per-example **precision**, **recall**, and **F1** and
aggregate **micro-/macro-averaged** variants.

Comparison baseline: [martian's published numbers](https://github.com/withmartian/code-review-benchmark)
(`step3_judge_comments.py`, Claude Opus judge).
