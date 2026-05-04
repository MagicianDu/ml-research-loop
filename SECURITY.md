# Security Policy

ML Research Loop executes local training code and can apply guarded client
patches inside an allowed workspace. Treat it as a local developer tool, not as
a remote multi-tenant sandbox.

## Supported Versions

| Version | Status |
| --- | --- |
| 0.1.x | Preview support |

## Reporting A Vulnerability

For public repositories, use GitHub private vulnerability reporting when it is
enabled. If that is not available, open a minimal public issue that describes
the affected component without exploit details, and request a maintainer
security contact.

## Security Boundaries

- Execution paths must stay inside the project root, `ML_RESEARCH_LOOP_ROOT`,
  or `ML_RESEARCH_LOOP_ALLOWED_ROOTS`.
- `clean_runtime_artifacts` requires explicit confirmation.
- `run_ai_autoresearch` is opt-in and requires explicit provider selection.
- API keys should be provided through environment variables, not committed to
  repository files.
- Do not run experiments from untrusted repositories without reviewing the
  generated workspace first.
