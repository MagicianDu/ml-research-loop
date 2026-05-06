# Official Proof Setup Bundle Spec

## Goal

Add a read-only setup bundle generator for official MLE-bench and PaperBench
debug/small proof runs. The bundle translates the current proof plan into
operator-facing files that can be used in a separate evaluation environment
without installing dependencies, downloading data, writing credentials, running
Docker, or claiming official scores from this product checkout.

## Scope

In scope:

- Build a structured setup bundle from `build_public_proof_plan()`.
- Include official source references for MLE-bench and PaperBench setup.
- Emit shell commands as setup instructions only; never execute them.
- Emit a redacted environment template with variable names and empty values.
- Emit artifact requirements for future proof-run publication.
- Write `official-proof-setup.json`, `official-proof-setup.md`, and
  `official-proof.env.example` when requested.
- Expose the bundle through script, CLI, MCP manifest, release check, and docs.

Out of scope:

- Installing `git-lfs`, `uv`, `mlebench`, Docker images, or Python packages.
- Cloning official benchmark repos.
- Downloading official data.
- Creating or reading secret values.
- Running official debug/dev/grade commands.
- Claiming official benchmark scores.

## Contract

The setup bundle payload must include:

- `status`: `blocked` or `ready_for_environment_setup`
- `read_only`: `true`
- `official_scores_claimed`: `false`
- `recommended_environment`
- `proof_plan`
- `references`
- `environment_template`
- `setup_sections`
- `artifact_manifest_template`
- `write_targets`

The markdown output must clearly say that it is a setup plan, not an official
score report.

## Acceptance

- `python3 scripts/benchmark_proof_setup.py --output-dir <tmp> --json` exits 0
  and writes JSON, markdown, and env example files.
- `ml-loop benchmark setup-bundle --output-dir <tmp> --json` is wired.
- `get_service_manifest()` includes `benchmark_proof_setup`.
- `scripts/release_check.py --json` includes `benchmark-proof-setup`.
- Tests verify the bundle never includes token-shaped secrets.
