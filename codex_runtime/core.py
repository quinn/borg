from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sarge import Capture, run
from codex_runtime.utils import (
    now_utc_iso,
    parse_json_lines,
    resolve_path,
    run_command_capture,
    shell_join,
    slugify,
    write_jsonl,
)


@dataclass(frozen=True)
class CodexExecRequest:
    prompt: str = "ping"
    workspace_folder: str = "."
    devcontainer_config: str = ".devcontainer/devcontainer.json"
    json_log_path: str = "logs/codex-run-events.jsonl"


@dataclass(frozen=True)
class CodexExecResult:
    ok: bool
    exit_code: int
    turn_status: str
    thread_id: str | None
    json_log_path: str
    summary_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "turn_status": self.turn_status,
            "thread_id": self.thread_id,
            "json_log_path": self.json_log_path,
            "summary_data": self.summary_data,
        }


@dataclass(frozen=True)
class CreateSessionRequest:
    session_name: str
    task_description: str
    workspace_folder: str = "."
    base_ref: str = "HEAD"
    sessions_root_path: str | None = None


@dataclass(frozen=True)
class CreateSessionResult:
    ok: bool
    session_id: str | None
    branch_name: str | None
    worktree_path: str | None
    devcontainer_config_path: str | None
    session_prompt: str
    setup_steps: list[dict[str, Any]]
    error: str | None

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


def summarize_events(
    command: str,
    exit_code: int,
    start_time: str,
    end_time: str,
    events: list[dict[str, Any]],
    non_json_stdout: list[str],
    stderr_lines: list[str],
) -> dict[str, Any]:
    summary_data: dict[str, Any] = {
        "command": command,
        "start_time": start_time,
        "end_time": end_time,
        "exit_code": exit_code,
        "thread_id": None,
        "turn_status": "unknown",
        "turn_error": None,
        "usage": None,
        "event_count": len(events),
        "agent_messages": [],
        "error_messages": [],
        "non_json_stdout_lines": non_json_stdout,
        "stderr_lines": stderr_lines,
    }

    for event in events:
        event_type = event.get("type")
        match event_type:
            case "thread.started":
                if summary_data["thread_id"] is None:
                    summary_data["thread_id"] = event.get("thread_id")
            case "turn.completed":
                summary_data["turn_status"] = "completed"
                usage_obj = event.get("usage")
                summary_data["usage"] = usage_obj if isinstance(usage_obj, dict) else None
            case "turn.failed":
                summary_data["turn_status"] = "failed"
                error_obj = event.get("error")
                if isinstance(error_obj, dict):
                    summary_data["turn_error"] = error_obj.get("message")
            case "error":
                message = event.get("message")
                if isinstance(message, str):
                    summary_data["error_messages"].append(message)
            case "item.completed":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str):
                        summary_data["agent_messages"].append(text)
            case _:
                pass

    return summary_data


def build_codex_command(request: CodexExecRequest) -> list[str]:
    workspace_path = str(Path(request.workspace_folder).resolve())
    config_path = str(resolve_path(workspace_path, request.devcontainer_config))
    codex_exec = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        request.prompt,
    ]
    return [
        "bunx",
        "@devcontainers/cli@latest",
        "exec",
        "--workspace-folder",
        workspace_path,
        "--config",
        config_path,
        *codex_exec,
    ]


def resolve_git_root(workspace_folder: str) -> tuple[str | None, str | None]:
    command = ["git", "-C", str(Path(workspace_folder).resolve()), "rev-parse", "--show-toplevel"]
    exit_code, stdout_text, stderr_text = run_command_capture(command)
    if exit_code != 0:
        return None, stderr_text.strip() or "Failed to resolve git root."
    git_root = stdout_text.strip()
    return git_root, None


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
    git_root, git_root_error = resolve_git_root(request.workspace_folder)
    if not git_root:
        return CreateSessionResult(
            ok=False,
            session_id=None,
            branch_name=None,
            worktree_path=None,
            devcontainer_config_path=None,
            session_prompt="",
            setup_steps=[],
            error=git_root_error,
        )

    git_root_path = Path(git_root)
    if request.sessions_root_path:
        sessions_root_path = resolve_path(str(git_root_path), request.sessions_root_path)
    else:
        sessions_root_path = (git_root_path.parent / f"{git_root_path.name}-sessions").resolve()
    sessions_root_path.mkdir(parents=True, exist_ok=True)

    session_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session_id = f"{slugify(request.session_name)}-{session_stamp}"
    branch_name = f"session/{session_id}"
    worktree_path = (sessions_root_path / session_id).resolve()
    devcontainer_config_path = (worktree_path / ".devcontainer" / "devcontainer.json").resolve()

    setup_steps: list[dict[str, Any]] = []

    worktree_cmd = [
        "git",
        "-C",
        str(git_root_path),
        "worktree",
        "add",
        "-b",
        branch_name,
        str(worktree_path),
        request.base_ref,
    ]
    worktree_exit, worktree_stdout, worktree_stderr = run_command_capture(worktree_cmd)
    setup_steps.append(
        {
            "name": "create_worktree",
            "command": shell_join(worktree_cmd),
            "exit_code": worktree_exit,
            "stdout_lines": worktree_stdout.splitlines(),
            "stderr_lines": worktree_stderr.splitlines(),
        }
    )
    if worktree_exit != 0:
        return CreateSessionResult(
            ok=False,
            session_id=session_id,
            branch_name=branch_name,
            worktree_path=str(worktree_path),
            devcontainer_config_path=str(devcontainer_config_path),
            session_prompt="",
            setup_steps=setup_steps,
            error="Failed to create git worktree.",
        )

    if not devcontainer_config_path.exists():
        return CreateSessionResult(
            ok=False,
            session_id=session_id,
            branch_name=branch_name,
            worktree_path=str(worktree_path),
            devcontainer_config_path=str(devcontainer_config_path),
            session_prompt="",
            setup_steps=setup_steps,
            error=f"Missing devcontainer config at {devcontainer_config_path}.",
        )

    up_cmd = [
        "bunx",
        "@devcontainers/cli@latest",
        "up",
        "--workspace-folder",
        str(worktree_path),
        "--config",
        str(devcontainer_config_path),
    ]
    up_exit, up_stdout, up_stderr = run_command_capture(up_cmd)
    setup_steps.append(
        {
            "name": "devcontainer_up",
            "command": shell_join(up_cmd),
            "exit_code": up_exit,
            "stdout_lines": up_stdout.splitlines(),
            "stderr_lines": up_stderr.splitlines(),
        }
    )

    session_prompt = build_session_prompt(
        task_description=request.task_description,
        session_id=session_id,
        worktree_path=str(worktree_path),
    )
    return CreateSessionResult(
        ok=up_exit == 0,
        session_id=session_id,
        branch_name=branch_name,
        worktree_path=str(worktree_path),
        devcontainer_config_path=str(devcontainer_config_path),
        session_prompt=session_prompt,
        setup_steps=setup_steps,
        error=None if up_exit == 0 else "Failed to start devcontainer for session worktree.",
    )


def execute_codex(request: CodexExecRequest) -> CodexExecResult:
    command_parts = build_codex_command(request)
    command = shell_join(command_parts)
    start_time = now_utc_iso()

    stdout_capture = Capture()
    stderr_capture = Capture()
    process = run(command, stdout=stdout_capture, stderr=stderr_capture)

    end_time = now_utc_iso()
    exit_code = int(process.returncode) if process.returncode is not None else 1

    stdout_lines = stdout_capture.text.splitlines() if stdout_capture.text else []
    stderr_lines = stderr_capture.text.splitlines() if stderr_capture.text else []
    events, non_json_stdout = parse_json_lines(stdout_lines)

    summary_data = summarize_events(
        command=command,
        exit_code=exit_code,
        start_time=start_time,
        end_time=end_time,
        events=events,
        non_json_stdout=non_json_stdout,
        stderr_lines=stderr_lines,
    )

    resolved_json_log_path = resolve_path(request.workspace_folder, request.json_log_path)
    write_jsonl(resolved_json_log_path, events)

    turn_status = str(summary_data.get("turn_status", "unknown"))
    thread_id = summary_data.get("thread_id")
    ok = exit_code == 0 and turn_status == "completed"
    return CodexExecResult(
        ok=ok,
        exit_code=exit_code,
        turn_status=turn_status,
        thread_id=thread_id if isinstance(thread_id, str) else None,
        json_log_path=str(resolved_json_log_path),
        summary_data=summary_data,
    )
