from __future__ import annotations

import shlex
import subprocess
import uuid

from deepagents.backends.protocol import ExecuteResponse
from deepagents.backends.sandbox import BaseSandbox


class K8sPodSandbox(BaseSandbox):
    def __init__(self, pod_name: str, namespace: str):
        self._pod_name = pod_name
        self._namespace = namespace

    @property
    def id(self) -> str:
        return self._pod_name

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        proc = subprocess.run(
            [
                "kubectl",
                "exec",
                "-n",
                self._namespace,
                self._pod_name,
                "--",
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


def _create_pod(image: str, namespace: str) -> str:
    pod_name = f"open-swe-{uuid.uuid4().hex[:12]}"
    create = subprocess.run(
        [
            "kubectl",
            "run",
            pod_name,
            "-n",
            namespace,
            "--image",
            image,
            "--restart",
            "Never",
            "--command",
            "--",
            "sleep",
            "infinity",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if create.returncode != 0:
        raise RuntimeError(f"Failed to create k8s pod sandbox: {create.stderr.strip()}")

    wait = subprocess.run(
        [
            "kubectl",
            "wait",
            "--for=condition=Ready",
            f"pod/{pod_name}",
            "-n",
            namespace,
            "--timeout=120s",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if wait.returncode != 0:
        raise RuntimeError(f"K8s pod sandbox did not become ready: {wait.stderr.strip()}")
    return pod_name


def _verify_pod_exists(pod_name: str, namespace: str) -> None:
    proc = subprocess.run(
        ["kubectl", "get", "pod", pod_name, "-n", namespace],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"K8s pod not found: {shlex.quote(pod_name)} in namespace {namespace}")


def create_k8s_pod_sandbox(sandbox_id: str | None = None):
    image = "open-swe-sandbox:latest"
    namespace = "default"
    if sandbox_id:
        _verify_pod_exists(sandbox_id, namespace)
        return K8sPodSandbox(sandbox_id, namespace)
    pod_name = _create_pod(image, namespace)
    return K8sPodSandbox(pod_name, namespace)
