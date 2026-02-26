mod irc 

devcontainer_config := ".devcontainer/devcontainer.json"
workspace_folder := "."

default:
  @just --list

devcontainer-up:
  bunx @devcontainers/cli@latest up --workspace-folder {{workspace_folder}} --config {{devcontainer_config}}

devcontainer-codex-version:
  bunx @devcontainers/cli@latest exec --workspace-folder {{workspace_folder}} --config {{devcontainer_config}} codex --version

devcontainer-codex-ping prompt="ping":
  bunx @devcontainers/cli@latest exec --workspace-folder {{workspace_folder}} --config {{devcontainer_config}} codex exec --skip-git-repo-check "{{prompt}}"

codex-mcp:
  uv run -m scripts.codex_mcp
