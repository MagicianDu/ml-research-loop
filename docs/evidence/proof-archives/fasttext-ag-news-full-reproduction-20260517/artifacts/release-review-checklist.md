# fastText Release Proof Review Checklist

## Claim Boundary

- downloadable local fastText proof bundle for review; not an official leaderboard score, full-paper reproduction claim, or general autonomous research improvement claim
- `official_scores_claimed=false` must remain true for every included artifact.

## Download Artifact

- Bundle: `release-proof-bundle.tar.gz`
- SHA-256: `7e48e9d50934d476bcd57dfdd6925db4eb4cd646fec2f9f76624108be16bbf45`
- Verify locally with `shasum -a 256 -c release-proof-bundle.sha256`.
- Inspect archive contents with `tar -tzf release-proof-bundle.tar.gz`.

## Review Checks

- Confirm the P4 proof manifest, artifact index, SHA256SUMS, and human review report are present.
- Confirm the P5 multi-round report is present when `multi_round_summary.included=true`.
- Confirm failures or rejected proposals are preserved instead of hidden.
- Confirm rollback events keep the best reviewed metric rather than promoting failed rounds.
- Confirm no public doc claims official leaderboard, full-paper reproduction, or arbitrary autonomous improvement.

## Included Multi-Round Summary

- Included: `True`
- Proposals: `2`
- Failed proposals: `1`
- Rollback events: `1`
- Best metric: `0.916`
