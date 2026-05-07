#!/usr/bin/env python3
"""Write a guarded benchmark proof publication bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import build_proof_publication_bundle, write_proof_publication_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a benchmark proof publication bundle")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    bundle = build_proof_publication_bundle(artifact_manifest, args.artifact_root)
    payload = write_proof_publication_bundle(bundle, args.output_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
