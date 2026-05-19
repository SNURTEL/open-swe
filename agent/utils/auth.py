"""GitHub authentication utilities."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_config
from langgraph.graph.state import RunnableConfig
from langgraph_sdk import get_client

from ..encryption import encrypt_token
from .github_app import get_github_app_installation_token_with_expiry
from .github_token import get_github_token_from_thread
from .linear import comment_on_linear_issue
from .slack import post_slack_ephemeral_message, post_slack_thread_reply

logger = logging.getLogger(__name__)

client = get_client()


async def leave_failure_comment(
    source: str,
    message: str,
) -> None:
    """Leave an auth failure comment for the appropriate source."""
    config = get_config()
    configurable = config.get("configurable", {})

    if source == "linear":
        linear_issue = configurable.get("linear_issue", {})
        issue_id = linear_issue.get("id") if isinstance(linear_issue, dict) else None
        if issue_id:
            logger.info(
                "Posting auth failure comment to Linear issue %s (source=%s)",
                issue_id,
                source,
            )
            await comment_on_linear_issue(issue_id, message)
        return
    if source == "slack":
        slack_thread = configurable.get("slack_thread", {})
        channel_id = slack_thread.get("channel_id") if isinstance(slack_thread, dict) else None
        thread_ts = slack_thread.get("thread_ts") if isinstance(slack_thread, dict) else None
        triggering_user_id = (
            slack_thread.get("triggering_user_id") if isinstance(slack_thread, dict) else None
        )
        if channel_id and thread_ts:
            if isinstance(triggering_user_id, str) and triggering_user_id:
                logger.info(
                    "Posting auth failure ephemeral reply to Slack user %s in channel %s thread %s",
                    triggering_user_id,
                    channel_id,
                    thread_ts,
                )
                sent = await post_slack_ephemeral_message(
                    channel_id=channel_id,
                    user_id=triggering_user_id,
                    text=message,
                    thread_ts=thread_ts,
                )
                if sent:
                    return
                logger.warning(
                    "Failed to post ephemeral auth failure reply for Slack user %s; falling back to thread reply",
                    triggering_user_id,
                )
            else:
                logger.warning(
                    "Missing Slack triggering_user_id for auth failure reply; falling back to thread reply",
                )
            logger.info(
                "Posting auth failure reply to Slack channel %s thread %s",
                channel_id,
                thread_ts,
            )
            await post_slack_thread_reply(channel_id, thread_ts, message)
        return
    if source == "github":
        logger.warning(
            "Auth failure for GitHub-triggered run (no token to post comment): %s", message
        )
        return
    raise ValueError(f"Unknown source: {source}")


async def persist_encrypted_github_token(
    thread_id: str, token: str, expires_at: str | None = None
) -> str:
    """Encrypt a GitHub token and store it (and its expiry) on the thread metadata."""
    encrypted = encrypt_token(token)
    metadata: dict[str, Any] = {
        "github_token_encrypted": encrypted,
        "github_token_expires_at": expires_at,
    }
    await client.threads.update(thread_id=thread_id, metadata=metadata)
    return encrypted


async def _resolve_bot_installation_token(thread_id: str) -> tuple[str, str, str | None]:
    """Get a GitHub App installation token and persist it for the thread."""
    bot_token, expires_at = await get_github_app_installation_token_with_expiry()
    if not bot_token:
        raise RuntimeError(
            "GitHub App is not configured. "
            "Set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, and GITHUB_APP_INSTALLATION_ID."
        )
    logger.info("Using GitHub App installation token for thread %s", thread_id)
    encrypted = await persist_encrypted_github_token(thread_id, bot_token, expires_at=expires_at)
    return bot_token, encrypted, expires_at


async def resolve_github_token(
    config: RunnableConfig, thread_id: str
) -> tuple[str, str, str | None]:
    """Resolve a GitHub token for the given thread.

    Checks the thread metadata for a cached (non-expired) token first.
    Falls back to a GitHub App installation token when no cached token
    is available.

    Returns:
        (github_token, new_encrypted, expires_at) tuple. ``expires_at`` is the
        ISO-8601 expiry persisted alongside the ciphertext, or ``None``.

    Raises:
        RuntimeError: If token resolution fails.
    """
    cached_token, cached_encrypted, cached_expires_at = await get_github_token_from_thread(
        thread_id
    )
    if cached_token and cached_encrypted:
        logger.info("Using cached GitHub token for thread %s", thread_id)
        return cached_token, cached_encrypted, cached_expires_at

    return await _resolve_bot_installation_token(thread_id)
