from __future__ import annotations

import shlex
import subprocess
import uuid

from deepagents.backends.protocol import ExecuteResponse
from deepagents.backends.sandbox import BaseSandbox


class DockerContainerSandbox(BaseSandbox):
    def __init__(self, container_id: str):
        self._container_id = container_id

    @property
    def id(self) -> str:
        return self._container_id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                self._container_id,
                "bash",
                "-lc",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return ExecuteResponse(
            output=(proc.stdout or "") + (proc.stderr or ""),
            exit_code=proc.returncode,
            truncated=False,
        )


def _create_container(image: str) -> str:
    name = f"open-swe-{uuid.uuid4().hex}"
    proc = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            image,
            "sleep",
            "infinity",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to create docker sandbox: {proc.stderr.strip()}")
    return (proc.stdout or "").strip()


def _verify_container_exists(container_id: str) -> None:
    proc = subprocess.run(
        ["docker", "inspect", "--type", "container", container_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"Docker container not found: {shlex.quote(container_id)}")


def create_docker_container_sandbox(sandbox_id: str | None = None):
    image = "open-swe-sandbox:latest"
    if sandbox_id:
        _verify_container_exists(sandbox_id)
        return DockerContainerSandbox(sandbox_id)
    container_id = _create_container(image)
    return DockerContainerSandbox(container_id)
