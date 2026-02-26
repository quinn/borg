#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codex_runtime.core import (
    CreateSessionRequest,
    EndSessionRequest,
    ListSessionsRequest,
    create_session,
    end_session,
    list_sessions,
)


mcp = FastMCP("codex-runtime")


@mcp.tool()
def create_codex_session(
    session_name: str,
    task_description: str,
    workspace_folder: str = ".",
    base_ref: str = "HEAD",
) -> dict[str, Any]:
    """Create isolated worktree + devcontainer and return a scoped sub-agent prompt."""
    request = CreateSessionRequest(
        session_name=session_name,
        task_description=task_description,
        workspace_folder=workspace_folder,
        base_ref=base_ref,
    )
    return create_session(request).to_dict()


@mcp.tool()
def end_codex_session(
    session_name: str,
    workspace_folder: str = ".",
) -> dict[str, Any]:
    """Tear down a session devcontainer and remove its worktree directory."""
    request = EndSessionRequest(
        session_name=session_name,
        workspace_folder=workspace_folder,
    )
    return end_session(request).to_dict()


@mcp.tool()
def list_codex_sessions(
    workspace_folder: str = ".",
) -> dict[str, Any]:
    """List active session worktrees under the repository sessions root."""
    request = ListSessionsRequest(workspace_folder=workspace_folder)
    return list_sessions(request).to_dict()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
