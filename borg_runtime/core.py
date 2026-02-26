from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sarge import shell_format
from borg_runtime.utils import run_command_capture, slugify


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
