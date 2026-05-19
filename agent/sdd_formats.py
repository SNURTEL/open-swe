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


def build_sdd_plan(*, plan_id: str, spec_id: str, spec_payload: dict[str, Any]) -> dict[str, Any]:
    requirements = spec_payload.get("Requirements", [])
    acceptance = spec_payload.get("AcceptanceCriteria", [])
    generated_tasks: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements, start=1):
        statement = ""
        if isinstance(requirement, dict):
            statement = str(requirement.get("statement", "")).strip()
        elif isinstance(requirement, str):
            statement = requirement.strip()
        if not statement:
            continue
        generated_tasks.append(
            {
                "task_id": f"TASK-{index}",
                "title": statement,
                "status": "pending",
                "exit_criteria": [f"Requirement satisfied: {statement}"],
            }
        )

    if not generated_tasks:
        problem_statement = (
            str(spec_payload.get("ProblemStatement", "")).strip() or "Complete issue"
        )
        generated_tasks = [
            {
                "task_id": "TASK-1",
                "title": problem_statement,
                "status": "pending",
                "exit_criteria": [f"Problem statement addressed: {problem_statement}"],
            }
        ]

    validation_task_id = f"TASK-{len(generated_tasks) + 1}"
    generated_tasks.append(
        {
            "task_id": validation_task_id,
            "title": "Validate implementation with repository checks",
            "status": "pending",
            "exit_criteria": ["Lint passes", "Tests pass"],
        }
    )

    dependencies: list[dict[str, str]] = []
    for idx in range(1, len(generated_tasks)):
        dependencies.append(
            {
                "from_task_id": f"TASK-{idx}",
                "to_task_id": f"TASK-{idx + 1}",
                "type": "blocks",
            }
        )

    definition_of_done: list[str] = []
    for criterion in acceptance:
        if isinstance(criterion, dict):
            statement = str(criterion.get("statement", "")).strip()
            if statement:
                definition_of_done.append(statement)
    if not definition_of_done:
        definition_of_done = [
            "Implementation merged with passing validation",
            "Required docs/config updates included",
        ]

    return {
        "PlanId": plan_id,
        "SpecId": spec_id,
        "Version": 1,
        "CreatedAt": _ts(),
        "Tasks": generated_tasks,
        "Dependencies": dependencies,
        "DefinitionOfDone": definition_of_done,
    }


def build_sdd_subtasks(
    *, subtasks_id: str, plan_id: str, plan_payload: dict[str, Any]
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    tasks = plan_payload.get("Tasks", [])
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id", f"TASK-{index}"))
        title = str(task.get("title", f"Complete {task_id}"))
        exit_criteria = task.get("exit_criteria", [])
        validation_steps = [str(step) for step in exit_criteria if str(step).strip()]
        if not validation_steps:
            validation_steps = [f"Task complete: {task_id}"]
        items.append(
            {
                "subtask_id": f"SUBTASK-{index}",
                "task_id": task_id,
                "title": title,
                "status": "pending",
                "validation_steps": validation_steps,
                "artifacts": [],
            }
        )

    return {
        "SubtasksId": subtasks_id,
        "PlanId": plan_id,
        "Version": 1,
        "CreatedAt": _ts(),
        "Items": items,
    }
