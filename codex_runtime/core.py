from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from sarge import shell_format
from codex_runtime.utils import run_command_capture, slugify


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


@dataclass(frozen=True)
class SessionContext:
    git_root_path: Path
    sessions_root_path: Path
    session_id: str
    branch_name: str
    worktree_path: Path
    devcontainer_config_path: Path


class CommandStepRecorder:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def run(self, name: str, command_format: str, *args: Any) -> tuple[int, str, str]:
        command = shell_format(command_format, *args)
        exit_code, stdout_text, stderr_text = run_command_capture(command)
        self.steps.append(
            {
                "name": name,
                "command": command,
                "exit_code": exit_code,
                "stdout_lines": stdout_text.splitlines(),
                "stderr_lines": stderr_text.splitlines(),
            }
        )
        return exit_code, stdout_text, stderr_text


def resolve_git_root(
    workspace_folder: str,
    recorder: CommandStepRecorder,
) -> tuple[str | None, str | None]:
    exit_code, stdout_text, stderr_text = recorder.run(
        "resolve_git_root",
        "git -C {0} rev-parse --show-toplevel",
        Path(workspace_folder).resolve(),
    )
    if exit_code != 0:
        return None, stderr_text.strip() or "Failed to resolve git root."
    git_root = stdout_text.strip()
    return git_root, None


def resolve_session_roots(
    workspace_folder: str,
    recorder: CommandStepRecorder,
) -> tuple[tuple[Path, Path] | None, str | None]:
    git_root, git_root_error = resolve_git_root(workspace_folder, recorder)
    if not git_root:
        return None, git_root_error

    git_root_path = Path(git_root)
    sessions_root_path = (git_root_path.parent / f"{git_root_path.name}-sessions").resolve()
    return (git_root_path, sessions_root_path), None


def parse_worktree_porcelain(stdout_text: str) -> list[tuple[Path, str | None]]:
    entries: list[tuple[Path, str | None]] = []
    current_path: Path | None = None
    current_branch: str | None = None

    for line in [*stdout_text.splitlines(), ""]:
        if line.startswith("worktree "):
            if current_path is not None:
                entries.append((current_path, current_branch))
            current_path = Path(line.removeprefix("worktree ").strip()).resolve()
            current_branch = None
            continue

        if line.startswith("branch "):
            branch_ref = line.removeprefix("branch ").strip()
            current_branch = branch_ref.removeprefix("refs/heads/")
            continue

        if not line and current_path is not None:
            entries.append((current_path, current_branch))
            current_path = None
            current_branch = None

    return entries


def resolve_session_context(
    session_name: str,
    workspace_folder: str,
    recorder: CommandStepRecorder,
) -> tuple[SessionContext | None, str | None]:
    roots, roots_error = resolve_session_roots(workspace_folder, recorder)
    if not roots:
        return None, roots_error

    git_root_path, sessions_root_path = roots
    session_id = slugify(session_name)
    branch_name = session_id
    worktree_path = (sessions_root_path / session_id).resolve()
    devcontainer_config_path = (worktree_path / ".devcontainer" / "devcontainer.json").resolve()
    return (
        SessionContext(
            git_root_path=git_root_path,
            sessions_root_path=sessions_root_path,
            session_id=session_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            devcontainer_config_path=devcontainer_config_path,
        ),
        None,
    )


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
