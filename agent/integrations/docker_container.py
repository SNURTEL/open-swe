from __future__ import annotations

import uuid

import docker
from deepagents.backends.protocol import ExecuteResponse
from deepagents.backends.sandbox import BaseSandbox
from docker.errors import DockerException, NotFound

from agent.config import get_settings


class DockerContainerSandbox(BaseSandbox):
    def __init__(self, container_id: str):
        self._container_id = container_id

    @property
    def id(self) -> str:
        return self._container_id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        client = docker.from_env(timeout=timeout)
        try:
            container = client.containers.get(self._container_id)
            result = container.exec_run(["bash", "-lc", command], demux=False)
        finally:
            client.close()
        output = result.output.decode("utf-8", errors="replace")
        return ExecuteResponse(
            output=output,
            exit_code=int(result.exit_code or 0),
            truncated=False,
        )


def _create_container(image: str) -> str:
    name = f"open-swe-{uuid.uuid4().hex[:16]}"
    client = docker.from_env()
    try:
        container = client.containers.run(
            image=image,
            command=["sleep", "infinity"],
            detach=True,
            remove=True,
            name=name,
        )
    except DockerException as exc:
        raise RuntimeError(f"Failed to create docker sandbox: {exc}") from exc
    finally:
        client.close()
    return container.id


def _verify_container_exists(container_id: str) -> None:
    client = docker.from_env()
    try:
        client.containers.get(container_id)
    except NotFound as exc:
        raise ValueError(f"Docker container not found: {container_id}") from exc
    except DockerException as exc:
        raise RuntimeError(f"Failed to inspect docker sandbox: {exc}") from exc
    finally:
        client.close()


def create_docker_container_sandbox(sandbox_id: str | None = None):
    image = get_settings().sandbox_image
    if not image:
        raise ValueError("SANDBOX_IMAGE must be set for docker-container sandbox")
    if sandbox_id:
        _verify_container_exists(sandbox_id)
        return DockerContainerSandbox(sandbox_id)
    container_id = _create_container(image)
    return DockerContainerSandbox(container_id)
