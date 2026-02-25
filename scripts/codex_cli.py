#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Sequence

from codex_runtime.core import CodexExecRequest, execute_codex


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run codex exec --json via the devcontainer and emit a parsed summary."
        )
    )
    parser.add_argument("prompt", nargs="?", default="ping", help="Prompt sent to codex exec.")
    parser.add_argument(
        "--workspace-folder",
        default=".",
        help="Workspace folder passed to devcontainer exec.",
    )
    parser.add_argument(
        "--devcontainer-config",
        default=".devcontainer/devcontainer.json",
        help="Devcontainer config path passed to devcontainer exec.",
    )
    parser.add_argument(
        "--json-log-path",
        "--json-log",
        dest="json_log_path",
        default="logs/codex-run-events.jsonl",
        help="Path for raw JSONL event output.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print parsed summary JSON to stdout (always returned by MCP).",
    )
    return parser


def args_to_request(args: argparse.Namespace) -> CodexExecRequest:
    return CodexExecRequest(
        prompt=args.prompt,
        workspace_folder=args.workspace_folder,
        devcontainer_config=args.devcontainer_config,
        json_log_path=args.json_log_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    request = args_to_request(args)
    result = execute_codex(request)
    if args.print_summary:
        print(json.dumps(result.summary_data, indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
