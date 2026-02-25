# AGENTS.md

## Ownership

You own this code base. You do not need to maintain interfaces, build adapters, etcetera, or other defensive coding practices. If something no longer makes sense, rip it out, destroy it, and replace it with something that does.

## Scope
- Applies to the repository root unless a deeper `AGENTS.md` overrides it.

## Project intent
- Primary goal: run Codex agents inside a dev container with host auth state mounted.
- Dev container config lives in `.devcontainer/`.
- `~/.codex` is mounted into the container at `/home/vscode/.codex`.

## Main commands
- `just devcontainer-up`
- `just devcontainer-codex-version`
- `just devcontainer-codex-ping`
- `just codex-run`
- `just codex-mcp`

## Runtime flow
- CLI entrypoint: `scripts/codex_cli.py` (arg parsing in script, business logic in `codex_runtime/core.py`).
- MCP entrypoint: `scripts/codex_mcp.py` (tool definitions in script, business logic in `codex_runtime/core.py`).
- Codex runs inside the devcontainer with `--dangerously-bypass-approvals-and-sandbox` (full unrestricted mode).
- MCP tools:
  - `create_codex_session`: creates a worktree, starts a devcontainer, and returns a scoped sub-agent prompt.
  - `codex_exec`: runs Codex in the session workspace and returns parsed summary data directly.
- Raw events: `logs/codex-run-events.jsonl`.
- Resume ID is `thread_id` in returned `summary_data`.

## Working conventions
- Keep changes minimal and declarative.
- Prefer scripted flows (`just`, `uv run`) over ad-hoc manual steps.
- Do not commit `logs/` artifacts unless explicitly requested.

## Escalation policy
- If a required command is likely to fail in sandbox (Docker socket, networked installs, Codex network calls), request escalation first.
- Do not loop through ad-hoc env-var retries before escalating.
- When escalating, keep command arguments minimal and avoid unnecessary env vars unless explicitly required.
