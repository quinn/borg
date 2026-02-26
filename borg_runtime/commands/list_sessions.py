from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from borg_runtime.core import (
    CommandStepRecorder,
    parse_worktree_porcelain,
    resolve_session_roots,
)


@dataclass(frozen=True)
class ListSessionsRequest:
    workspace_folder: str = "."


@dataclass(frozen=True)
class ListSessionsResult:
    ok: bool = False
    sessions_root_path: str | None = None
    sessions: list[dict[str, Any]] = field(default_factory=list)
    list_steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "sessions_root_path": self.sessions_root_path,
            "sessions": self.sessions,
            "list_steps": self.list_steps,
            "error": self.error,
        }


def list_sessions(request: ListSessionsRequest) -> ListSessionsResult:
    recorder = CommandStepRecorder()
    base_result = replace(
        ListSessionsResult(),
        list_steps=recorder.steps,
    )

    roots, roots_error = resolve_session_roots(request.workspace_folder, recorder)
    if not roots:
        return replace(base_result, error=roots_error)

    git_root_path, sessions_root_path = roots
    base_result = replace(
        base_result,
        sessions_root_path=str(sessions_root_path),
    )
    list_worktrees_exit, list_worktrees_stdout, _ = recorder.run(
        "list_git_worktrees",
        "git -C {0} worktree list --porcelain",
        git_root_path,
    )
    if list_worktrees_exit != 0:
        return replace(base_result, error="Failed to list git worktrees.")

    sessions: list[dict[str, Any]] = []
    for worktree_path, branch_name in parse_worktree_porcelain(list_worktrees_stdout):
        try:
            worktree_path.relative_to(sessions_root_path)
        except ValueError:
            continue

        devcontainer_config_path = (worktree_path / ".devcontainer" / "devcontainer.json").resolve()
        sessions.append(
            {
                "session_id": worktree_path.name,
                "branch_name": branch_name,
                "worktree_path": str(worktree_path),
                "devcontainer_config_path": str(devcontainer_config_path),
                "has_devcontainer_config": devcontainer_config_path.exists(),
            }
        )

    sessions.sort(key=lambda session: str(session["session_id"]))
    return replace(
        base_result,
        ok=True,
        sessions=sessions,
        error=None,
    )
