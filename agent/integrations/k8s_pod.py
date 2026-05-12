from __future__ import annotations

import time
import uuid

from deepagents.backends.protocol import ExecuteResponse
from deepagents.backends.sandbox import BaseSandbox
from kubernetes import client, config
from kubernetes.client import ApiException
from kubernetes.config.config_exception import ConfigException
from kubernetes.stream import stream

from agent.config import get_settings

_EXIT_MARKER = "__OPEN_SWE_EXIT_CODE__:"


class K8sPodSandbox(BaseSandbox):
    def __init__(self, pod_name: str, namespace: str):
        self._pod_name = pod_name
        self._namespace = namespace

    @property
    def id(self) -> str:
        return self._pod_name

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        api = client.CoreV1Api()
        wrapped = (
            f"{command}\n"
            "__OPEN_SWE_RC=$?\n"
            f"printf '\\n{_EXIT_MARKER}%s\\n' \"$__OPEN_SWE_RC\"\n"
            'exit "$__OPEN_SWE_RC"'
        )
        output = stream(
            api.connect_get_namespaced_pod_exec,
            self._pod_name,
            self._namespace,
            command=["bash", "-lc", wrapped],
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _request_timeout=timeout,
        )
        exit_code = 0
        if _EXIT_MARKER in output:
            output, marker = output.rsplit(_EXIT_MARKER, 1)
            marker_line = marker.strip().splitlines()[0] if marker.strip() else "1"
            try:
                exit_code = int(marker_line)
            except ValueError:
                exit_code = 1
        return ExecuteResponse(
            output=output,
            exit_code=exit_code,
            truncated=False,
        )


def _load_k8s_config() -> None:
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()


def _wait_for_pod_ready(
    api: client.CoreV1Api, pod_name: str, namespace: str, timeout_seconds: int
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        if pod.status and pod.status.phase == "Running":
            conditions = pod.status.conditions or []
            if any(c.type == "Ready" and c.status == "True" for c in conditions):
                return
        time.sleep(1)
    raise RuntimeError(f"K8s pod sandbox did not become ready: {pod_name}")


def _create_pod(image: str, namespace: str) -> str:
    pod_name = f"open-swe-{uuid.uuid4().hex[:16]}"
    api = client.CoreV1Api()
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "open-swe-sandbox"}),
        spec=client.V1PodSpec(
            restart_policy="Never",
            containers=[
                client.V1Container(
                    name="sandbox",
                    image=image,
                    command=["sleep", "infinity"],
                )
            ],
        ),
    )
    try:
        api.create_namespaced_pod(namespace=namespace, body=pod)
    except ApiException as exc:
        raise RuntimeError(f"Failed to create k8s pod sandbox: {exc}") from exc
    _wait_for_pod_ready(api, pod_name, namespace, timeout_seconds=120)
    return pod_name


def _verify_pod_exists(pod_name: str, namespace: str) -> None:
    api = client.CoreV1Api()
    try:
        api.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError(f"K8s pod not found: {pod_name} in namespace {namespace}") from exc
        raise RuntimeError(f"Failed to inspect k8s pod sandbox: {exc}") from exc


def create_k8s_pod_sandbox(sandbox_id: str | None = None):
    settings = get_settings()
    image = settings.sandbox_image
    if not image:
        raise ValueError("SANDBOX_IMAGE must be set for k8s-pod sandbox")
    namespace = settings.sandbox_k8s_namespace
    _load_k8s_config()
    if sandbox_id:
        _verify_pod_exists(sandbox_id, namespace)
        return K8sPodSandbox(sandbox_id, namespace)
    pod_name = _create_pod(image, namespace)
    return K8sPodSandbox(pod_name, namespace)
