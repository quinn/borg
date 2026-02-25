#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codex_runtime.core import (
    CodexExecRequest,
    CreateSessionRequest,
    create_session,
    execute_codex,
)


mcp = FastMCP("codex-runtime")


@mcp.tool()
def codex_exec(
    prompt: str = "ping",
    workspace_folder: str = ".",
    devcontainer_config: str = ".devcontainer/devcontainer.json",
    json_log_path: str = "logs/codex-run-events.jsonl",
) -> dict[str, Any]:
    """Run codex in a devcontainer and return status + parsed summary data."""
    request = CodexExecRequest(
        prompt=prompt,
        workspace_folder=workspace_folder,
        devcontainer_config=devcontainer_config,
        json_log_path=json_log_path,
    )
    return execute_codex(request).to_dict()


@mcp.tool()
def create_codex_session(
    session_name: str,
    task_description: str,
    workspace_folder: str = ".",
    base_ref: str = "HEAD",
    sessions_root_path: str | None = None,
) -> dict[str, Any]:
    """Create isolated worktree + devcontainer and return a scoped sub-agent prompt."""
    request = CreateSessionRequest(
        session_name=session_name,
        task_description=task_description,
        workspace_folder=workspace_folder,
        base_ref=base_ref,
        sessions_root_path=sessions_root_path,
    )
    return create_session(request).to_dict()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
