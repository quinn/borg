set shell := ["bash", "-cu"]

compose_file := "irc.compose.yaml"
project_name := "openclaw-irc"
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

codex-run prompt="ping":
  uv run -m scripts.codex_cli --print-summary "{{prompt}}"

codex-mcp:
  uv run -m scripts.codex_mcp

irc-up:
  docker compose -f {{compose_file}} -p {{project_name}} up -d

irc-down:
  docker compose -f {{compose_file}} -p {{project_name}} down

irc-ps:
  docker compose -f {{compose_file}} -p {{project_name}} ps

irc-logs:
  docker compose -f {{compose_file}} -p {{project_name}} logs -f --tail=200 ngircd

irc-restart:
  docker compose -f {{compose_file}} -p {{project_name}} restart ngircd
