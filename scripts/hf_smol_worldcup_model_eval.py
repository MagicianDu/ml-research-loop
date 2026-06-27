"""Run Smol AI WorldCup through an OpenAI-compatible model provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import write_smol_worldcup_model_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local OpenAI-compatible model on Smol AI WorldCup and write P2 artifacts."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    parser.add_argument("--api-key-env")
    parser.add_argument(
        "--thinking-mode",
        default="default",
        choices=["default", "enabled", "disabled"],
    )
    parser.add_argument("--reasoning-effort", choices=["high", "max"])
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--row-id",
        action="append",
        default=[],
        help="Restrict model eval to specific Smol WorldCup row ids; repeatable.",
    )
    parser.add_argument(
        "--cached-response-prediction-path",
        type=Path,
        help="Replay model responses from a previous prediction.jsonl response cache.",
    )
    parser.add_argument(
        "--require-cached-responses",
        action="store_true",
        help="Fail if any selected row is missing from the cached response predictions.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--round-id", default="round-001")
    parser.add_argument(
        "--prompt-profile",
        default="default",
        choices=[
            "default",
            "p3-routing-v1",
            "p3-dev-v2",
            "p3-semantic-v1",
            "p3-semantic-v2",
            "p3-canary-repair-v1",
            "p3-canary-repair-v2",
            "p3-canary-repair-v3",
            "p3-canary-repair-v4",
            "p3-canary-repair-v5",
            "p3-canary-repair-v6",
            "p3-canary-repair-v7",
            "p3-slice-metacognition-textgrad-v1",
            "p3-v7-metacognition-textgrad-v2",
            "p3-v7-metacognition-textgrad-pw-ar-v3",
        ],
    )
    parser.add_argument(
        "--prompt-profile-registration",
        type=Path,
        help="PromptProfileRegistration artifact used as a dynamic profile overlay.",
    )
    parser.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
    )
    parser.add_argument("--canary-fraction", type=float, default=0.2)
    parser.add_argument(
        "--judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
    )
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-base-url")
    parser.add_argument("--model-size-billion", type=float, default=20.0)
    parser.add_argument("--estimated-ram-gb", type=float, default=32.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = args.base_url
    if args.model_provider == "deepseek" and base_url == "http://127.0.0.1:1234/v1":
        base_url = "https://api.deepseek.com"
    payload = write_smol_worldcup_model_eval(
        args.output_dir,
        timeout_seconds=args.timeout_seconds,
        page_size=args.page_size,
        limit=args.limit,
        row_ids=args.row_id,
        model=args.model,
        base_url=base_url,
        model_provider=args.model_provider,
        api_key_env=args.api_key_env,
        thinking_mode=args.thinking_mode,
        reasoning_effort=args.reasoning_effort,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        round_id=args.round_id,
        prompt_profile=args.prompt_profile,
        prompt_profile_registration=args.prompt_profile_registration,
        evaluation_split=args.evaluation_split,
        canary_fraction=args.canary_fraction,
        cached_response_prediction_path=args.cached_response_prediction_path,
        require_cached_responses=args.require_cached_responses,
        judge_mode=args.judge_mode,
        judge_model=args.judge_model,
        judge_base_url=args.judge_base_url,
        model_size_billion=args.model_size_billion,
        estimated_ram_gb=args.estimated_ram_gb,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


if __name__ == "__main__":
    raise SystemExit(main())
