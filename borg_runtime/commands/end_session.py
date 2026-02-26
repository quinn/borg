from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from borg_runtime.core import (
    CommandStepRecorder,
    parse_worktree_porcelain,
    resolve_session_context,
)


@dataclass(frozen=True)
class EndSessionRequest:
    session_name: str
    workspace_folder: str = "."


@dataclass(frozen=True)
class EndSessionResult:
    ok: bool = False
    session_id: str | None = None
    branch_name: str | None = None
    worktree_path: str | None = None
    teardown_steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "worktree_path": self.worktree_path,
            "teardown_steps": self.teardown_steps,
            "error": self.error,
        }


def end_session(request: EndSessionRequest) -> EndSessionResult:
    recorder = CommandStepRecorder()
    base_result = replace(
        EndSessionResult(),
        teardown_steps=recorder.steps,
    )

    context, context_error = resolve_session_context(
        request.session_name, request.workspace_folder, recorder
    )
    if not context:
        return replace(base_result, error=context_error)

    base_result = replace(
        base_result,
        session_id=context.session_id,
        branch_name=context.branch_name,
        worktree_path=str(context.worktree_path),
    )

    def fail(error: str) -> EndSessionResult:
        return replace(base_result, error=error)

    list_containers_exit, list_containers_stdout, _ = recorder.run(
        "list_devcontainer_containers",
        "docker ps -aq --filter {0}",
        f"label=devcontainer.local_folder={context.worktree_path}",
    )
    if list_containers_exit != 0:
        return fail("Failed to list devcontainer containers for session.")

    container_ids = [line.strip() for line in list_containers_stdout.splitlines() if line.strip()]
    if container_ids:
        ids_placeholders = " ".join("{"+str(index)+"}" for index in range(len(container_ids)))
        remove_containers_exit, _, _ = recorder.run(
            "remove_devcontainer_containers",
            f"docker rm -f {ids_placeholders}",
            *container_ids,
        )
        if remove_containers_exit != 0:
            return fail("Failed to remove devcontainer containers for session.")

    list_worktrees_exit, list_worktrees_stdout, _ = recorder.run(
        "list_git_worktrees",
        "git -C {0} worktree list --porcelain",
        context.git_root_path,
    )
    if list_worktrees_exit != 0:
        return fail("Failed to list git worktrees.")

    is_registered_worktree = any(
        candidate == context.worktree_path
        for candidate, _ in parse_worktree_porcelain(list_worktrees_stdout)
    )
    if is_registered_worktree:
        remove_worktree_exit, _, _ = recorder.run(
            "remove_git_worktree",
            "git -C {0} worktree remove --force {1}",
            context.git_root_path,
            context.worktree_path,
        )
        if remove_worktree_exit != 0:
            return fail("Failed to remove git worktree.")

    if context.worktree_path.exists():
        remove_directory_exit, _, _ = recorder.run(
            "remove_worktree_directory",
            "rm -rf {0}",
            context.worktree_path,
        )
        if remove_directory_exit != 0:
            return fail("Failed to remove worktree directory.")

    return replace(
        base_result,
        ok=True,
        error=None,
    )
