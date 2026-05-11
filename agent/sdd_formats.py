"""Strict SDD artifact builders."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def build_sdd_spec(
    *,
    spec_id: str,
    issue: dict[str, Any],
    issue_title: str,
    issue_body: str,
    comments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "SpecId": spec_id,
        "Version": 1,
        "CreatedAt": _ts(),
        "Issue": issue,
        "ProblemStatement": issue_title,
        "Context": {
            "description": issue_body,
            "comment_count": len(comments),
        },
        "Requirements": [
            {"id": "REQ-1", "statement": "Implement requested behavior from issue context"},
            {"id": "REQ-2", "statement": "Preserve existing repository conventions and tests"},
        ],
        "Constraints": [
            "Use existing repo tooling for lint/test",
            "Keep changes focused and minimal for requested behavior",
        ],
        "AcceptanceCriteria": [
            {"id": "AC-1", "statement": "Code changes compile/lint and test successfully"},
            {"id": "AC-2", "statement": "PR artifacts updated with implementation summary"},
        ],
        "Risks": [
            {"id": "RISK-1", "description": "Behavioral regressions", "mitigation": "Run tests"},
        ],
    }


def build_sdd_plan(*, plan_id: str, spec_id: str) -> dict[str, Any]:
    return {
        "PlanId": plan_id,
        "SpecId": spec_id,
        "Version": 1,
        "CreatedAt": _ts(),
        "Tasks": [
            {
                "task_id": "TASK-1",
                "title": "Analyze issue requirements and impacted modules",
                "status": "pending",
                "exit_criteria": ["Impacted modules identified"],
            },
            {
                "task_id": "TASK-2",
                "title": "Implement focused code changes",
                "status": "pending",
                "exit_criteria": ["Code updated in impacted modules"],
            },
            {
                "task_id": "TASK-3",
                "title": "Validate with lint and tests",
                "status": "pending",
                "exit_criteria": ["Lint and tests pass"],
            },
        ],
        "Dependencies": [
            {"from_task_id": "TASK-1", "to_task_id": "TASK-2", "type": "blocks"},
            {"from_task_id": "TASK-2", "to_task_id": "TASK-3", "type": "blocks"},
        ],
        "DefinitionOfDone": [
            "Implementation merged with passing validation",
            "Required docs/config updates included",
        ],
    }


def build_sdd_subtasks(*, subtasks_id: str, plan_id: str) -> dict[str, Any]:
    return {
        "SubtasksId": subtasks_id,
        "PlanId": plan_id,
        "Version": 1,
        "CreatedAt": _ts(),
        "Items": [
            {
                "subtask_id": "SUBTASK-1",
                "task_id": "TASK-1",
                "title": "Parse issue and comments",
                "status": "pending",
                "validation_steps": ["Issue context parsed"],
                "artifacts": [],
            },
            {
                "subtask_id": "SUBTASK-2",
                "task_id": "TASK-2",
                "title": "Apply implementation changes",
                "status": "pending",
                "validation_steps": ["Code diff created"],
                "artifacts": [],
            },
            {
                "subtask_id": "SUBTASK-3",
                "task_id": "TASK-3",
                "title": "Run lint and tests",
                "status": "pending",
                "validation_steps": ["Lint pass", "Test pass"],
                "artifacts": [],
            },
        ],
    }
