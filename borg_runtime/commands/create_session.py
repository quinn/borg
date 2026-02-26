from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from borg_runtime.core import CommandStepRecorder, resolve_session_context


@dataclass(frozen=True)
class CreateSessionRequest:
    session_name: str
    task_description: str
    workspace_folder: str = "."
    base_ref: str = "HEAD"


@dataclass(frozen=True)
class CreateSessionResult:
    ok: bool = False
    session_id: str | None = None
    branch_name: str | None = None
    worktree_path: str | None = None
    devcontainer_config_path: str | None = None
    session_prompt: str = ""
    setup_steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "worktree_path": self.worktree_path,
            "devcontainer_config_path": self.devcontainer_config_path,
            "session_prompt": self.session_prompt,
            "setup_steps": self.setup_steps,
            "error": self.error,
        }


def build_session_prompt(task_description: str, session_id: str, worktree_path: str) -> str:
    scope = task_description.strip()
    return (
        f"You are a sub-agent for session `{session_id}`.\n\n"
        "Scope:\n"
        f"{scope}\n\n"
        "Execution rules:\n"
        "- Work only on the scope above.\n"
        "- Keep changes focused and minimal.\n"
        "- Run relevant checks for your changes.\n"
        "- If you are blocked or stuck, stop and return immediately.\n\n"
        "Final response format (required):\n"
        "- status: completed | blocked\n"
        "- work_done: concise summary\n"
        "- files_changed: list\n"
        "- blockers: list or \"none\"\n"
        "- next_steps: list or \"none\"\n\n"
        f"Workspace: {worktree_path}\n"
    )


def create_session(request: CreateSessionRequest) -> CreateSessionResult:
    recorder = CommandStepRecorder()
    base_result = replace(
        CreateSessionResult(),
        setup_steps=recorder.steps,
    )

    context, context_error = resolve_session_context(
        request.session_name, request.workspace_folder, recorder
    )
    if not context:
        return replace(base_result, error=context_error)

    context.sessions_root_path.mkdir(parents=True, exist_ok=True)
    base_result = replace(
        base_result,
        session_id=context.session_id,
        branch_name=context.branch_name,
        worktree_path=str(context.worktree_path),
        devcontainer_config_path=str(context.devcontainer_config_path),
    )

    def fail(error: str) -> CreateSessionResult:
        return replace(base_result, error=error)

    worktree_exit, _, _ = recorder.run(
        "create_worktree",
        "git -C {0} worktree add -b {1} {2} {3}",
        context.git_root_path,
        context.branch_name,
        context.worktree_path,
        request.base_ref,
    )
    if worktree_exit != 0:
        return fail("Failed to create git worktree.")

    if not context.devcontainer_config_path.exists():
        return fail(f"Missing devcontainer config at {context.devcontainer_config_path}.")

    up_exit, _, _ = recorder.run(
        "devcontainer_up",
        "bunx @devcontainers/cli@latest up --workspace-folder {0} --config {1}",
        context.worktree_path,
        context.devcontainer_config_path,
    )

    session_prompt = build_session_prompt(
        task_description=request.task_description,
        session_id=context.session_id,
        worktree_path=str(context.worktree_path),
    )
    return replace(
        base_result,
        ok=up_exit == 0,
        session_prompt=session_prompt,
        error=None if up_exit == 0 else "Failed to start devcontainer for session worktree.",
    )
