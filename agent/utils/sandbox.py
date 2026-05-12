import os

from agent.config import get_settings
from agent.integrations.docker_container import create_docker_container_sandbox
from agent.integrations.k8s_pod import create_k8s_pod_sandbox
from agent.integrations.local import create_local_sandbox

SANDBOX_FACTORIES = {
    "docker-container": create_docker_container_sandbox,
    "k8s-pod": create_k8s_pod_sandbox,
    "local": create_local_sandbox,
}


def create_sandbox(sandbox_id: str | None = None):
    """Create or reconnect to a sandbox using the configured provider.

    The provider is selected via the SANDBOX_TYPE environment variable.
    Supported values: docker-container (default), k8s-pod, local.

    Args:
        sandbox_id: Optional existing sandbox ID to reconnect to.

    Returns:
        A sandbox backend implementing SandboxBackendProtocol.
    """
    sandbox_type = get_settings().sandbox_type or os.getenv("SANDBOX_TYPE", "docker-container")
    factory = SANDBOX_FACTORIES.get(sandbox_type)
    if not factory:
        supported = ", ".join(sorted(SANDBOX_FACTORIES))
        raise ValueError(f"Invalid sandbox type: {sandbox_type}. Supported types: {supported}")
    return factory(sandbox_id)


def validate_sandbox_startup_config() -> None:
    """Validate the configured sandbox provider's env vars at server startup.

    Raises ValueError if the active provider's configuration is invalid.
    Called from the FastAPI lifespan hook so errors surface at boot rather
    than on the first sandbox creation.
    """
    sandbox_type = get_settings().sandbox_type or os.getenv("SANDBOX_TYPE", "docker-container")
    if sandbox_type not in SANDBOX_FACTORIES:
        supported = ", ".join(sorted(SANDBOX_FACTORIES))
        raise ValueError(f"Invalid sandbox type: {sandbox_type}. Supported types: {supported}")
