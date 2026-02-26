# AGENTS.md

## Ownership

You own this code base. You do not need to maintain interfaces, build adapters, etcetera, or other defensive coding practices. If something no longer makes sense, rip it out, destroy it, and replace it with something that does.

## Scope
- Applies to the repository root unless a deeper `AGENTS.md` overrides it.

## Project intent
- Primary goal: run Codex and Claude Code agents inside a dev container with host auth state mounted.
- Dev container config lives in `.devcontainer/`.
- Packages are declared in `.devcontainer/flake.nix` (Nix flake with `buildEnv`).
- `~/.codex` is mounted into the container at `/home/vscode/.codex`.
- `~/.claude` and `~/.claude.json` are mounted into the container at `/home/vscode/.claude` and `/home/vscode/.claude.json`.

## Main commands
- `just devcontainer-up`
- `just devcontainer-codex-version`
- `just devcontainer-codex-ping`
- `just devcontainer-claude-version`
- `just devcontainer-claude-ping`
- `just mcp`

## Runtime flow
- MCP entrypoint: `scripts/mcp_server.py` (tool definitions in script, business logic in `borg_runtime/core.py`).
- Codex runs inside the devcontainer with `--dangerously-bypass-approvals-and-sandbox` (full unrestricted mode).
- Claude Code runs inside the devcontainer with `--dangerously-skip-permissions` (full unrestricted mode).
- MCP tools (each accepts an `agent` parameter — `"claude"` or `"codex"`):
  - `create_session_tool`: creates a worktree, starts a devcontainer, and returns a scoped sub-agent prompt.
  - `end_session_tool`: tears down a session devcontainer and removes its worktree directory.
  - `list_sessions_tool`: lists active session worktrees under the repository sessions root.

## Working conventions
- Keep changes minimal and declarative.
- Prefer scripted flows (`just`, `uv run`) over ad-hoc manual steps.
- Do not commit `logs/` artifacts unless explicitly requested.

## Escalation policy
- If a required command is likely to fail in sandbox (Docker socket, networked installs, Codex network calls), request escalation first.
- Do not loop through ad-hoc env-var retries before escalating.
- When escalating, keep command arguments minimal and avoid unnecessary env vars unless explicitly required.
