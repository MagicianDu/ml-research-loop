# Proof Release Evidence Index

schema_version: `2026-05-12.proof-release-index.v1`
official_scores_claimed: `false`
entry_count: `5`

This index records local proof archive evidence. It does not promote local proof runs as official benchmark results.

## memflow-real-paper-20260517

- description: MemFlow bounded public mini-slice real-paper pilot proof
- proof_archive: `docs/evidence/proof-archives/memflow-real-paper-20260517/proof-archive.json`
- artifact_index: `docs/evidence/proof-archives/memflow-real-paper-20260517/artifact-index.json`
- publication_guard: `docs/evidence/proof-archives/memflow-real-paper-20260517/publication/proof-publication.json`
- status: `archivable`
- publication_status: `publishable_with_limitations`
- benchmark_name: `real_paper_pilot`
- run_mode: `local_public_data`
- judge_type: `operator_artifact_review`
- metric: `selection_accuracy`
- official_scores_claimed: `false`

### Allowed Public Claims

- local real-paper pilot proof artifacts are available
- bounded metric before/after, review status, and limitations are published

### Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance
- arbitrary paper reproduction or automatic guaranteed improvement

### Artifact SHA256 Summary

- `paper_selection_report` `artifacts/paper-selection-report.json` sha256: `0c8b5af0ae42023400464cf8f4bc66b99acaf4bb7990b96e16420915177720ab`
- `research_case` `artifacts/research-case.json` sha256: `1015f76f27a327c935490bb18e8fca85d11f009a6c1fa2e4224d8c351167e080`
- `environment_probe` `artifacts/environment-probe.json` sha256: `d1b89ecdb040cd3e39ef02c69c3957fe8a52faa0a38ba8c17aec681b60817ee8`
- `dataset_provenance` `artifacts/dataset-provenance.json` sha256: `cbc0999196a42f972e214593a0723ac29b62d17f0f2f061813a2d5a8facccf66`
- `baseline_metrics` `artifacts/baseline-metrics.json` sha256: `dc6aa4275d2405273f810149b53d558eb031c95041253e27c134ccdf5601116f`
- `ablation_metrics` `artifacts/ablation-metrics.json` sha256: `c245c4f20d3fa920d20f0142b936d37eb0594f4f622c224f7aec01eb60c050b5`
- `experiment_summary` `artifacts/experiment-summary.json` sha256: `ec895346c8e06cd2a234a9d9e58f0701d0de291ccb3fc2b1e6ed26181aa3b9b5`
- `run_log` `artifacts/run-log.txt` sha256: `0e2dc51a8153978db9a16835c58e815352dd143303aa5d2247bf51000335074d`
- `client_handoff` `artifacts/client-handoff.json` sha256: `e9188211dffeaffbaa64d6a54e67ab0421dfea79bd6eafd3dbb59a5bd686894a`
- `client_routing_patch` `artifacts/client-routing-patch.json` sha256: `a0f1d83fabafa36b1c67ee4e6a41277e4b00eb881a3da5e6aec2a0dc3e4b0b58`
- `patched_metrics` `artifacts/patched-metrics.json` sha256: `b6525d864b9f6d1d40b430675c97f8adbe04d0a7b07f39de98fb57978a807e82`
- `iteration_comparison` `artifacts/iteration-comparison.json` sha256: `ee4b90b8c3bb58c2f1a578d36fd923989c8eef64699a70e99b60a352bcc0c077`
- `human_review_report` `artifacts/human-review-report.json` sha256: `4b70780de8d1994dfdb8fad1bf7bb377ad5a9fd1f403cc694bf4af7011689c2f`

### Limitations

- curated public mini-slice derived from arXiv metadata; not an official benchmark result
- single bounded claim only; not a full paper reproduction
- local deterministic routing heuristic; no external judge or official scorer
- local proof is not an official benchmark result

## adam-real-paper-20260517

- description: Adam bounded public mini-slice real-paper pilot proof
- proof_archive: `docs/evidence/proof-archives/adam-real-paper-20260517/proof-archive.json`
- artifact_index: `docs/evidence/proof-archives/adam-real-paper-20260517/artifact-index.json`
- publication_guard: `docs/evidence/proof-archives/adam-real-paper-20260517/publication/proof-publication.json`
- status: `archivable`
- publication_status: `publishable_with_limitations`
- benchmark_name: `real_paper_pilot`
- run_mode: `local_public_data`
- judge_type: `operator_artifact_review`
- metric: `optimizer_progress_score`
- official_scores_claimed: `false`

### Allowed Public Claims

- local real-paper pilot proof artifacts are available
- bounded metric before/after, review status, and limitations are published

### Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance
- arbitrary paper reproduction or automatic guaranteed improvement

### Artifact SHA256 Summary

- `paper_selection_report` `artifacts/paper-selection-report.json` sha256: `05915e0d19c9a03a1e34d4d8b705e5ff5be45a63a557b92703602bacca2d1c00`
- `research_case` `artifacts/research-case.json` sha256: `53f295d3d4a642b91bd65efe1b992446a198084f9cd070587672445ed8db1015`
- `environment_probe` `artifacts/environment-probe.json` sha256: `5471a6e61a0c4f163aab03a7a2fb53c74ba93b3338ddfb2d868874c925f69801`
- `dataset_provenance` `artifacts/dataset-provenance.json` sha256: `a30993ec65ebb719b0b9a57bebf762bae8558236e61040a3271ecf5999eb0db6`
- `baseline_metrics` `artifacts/baseline-metrics.json` sha256: `b3ab08f2ae1beacaf1922ba10e72bc3659e8fd6184780c10d8780fb612e8b66f`
- `ablation_metrics` `artifacts/ablation-metrics.json` sha256: `3aea15267ef8e6c67333aa7f9fa41b71e5fdcc8cd955ca27f82a716dc5d42677`
- `experiment_summary` `artifacts/experiment-summary.json` sha256: `738490b618d4020687dd4676e5868c701a98e0c25c47cf96d4cb49396c8794a8`
- `run_log` `artifacts/run-log.txt` sha256: `352282feefc27ce35b558c3a0d656eaa52968152adbcde428e2c1bf0b922ee2a`
- `client_handoff` `artifacts/client-handoff.json` sha256: `571697006d32769f72be88f912eda6f317b81986fcb012f09141d940f669a53d`
- `client_routing_patch` `artifacts/client-routing-patch.json` sha256: `3fe24366344d202dc11b33b32bed8d4b6839c030275d0360dc8ee8bf0e1fe757`
- `patched_metrics` `artifacts/patched-metrics.json` sha256: `e4c8f0f1cb143c836845cb6d2df9ee9e42a18a2dcdd8c64b80df94ec2177e32a`
- `iteration_comparison` `artifacts/iteration-comparison.json` sha256: `b2f24aacac3098e2c553a8418412e25e8fb88e50190c7c316f587145177ee009`
- `human_review_report` `artifacts/human-review-report.json` sha256: `4011fec8274d55f7df41e9668014f2ac86d287fa30d7a6ef41be870934e716a0`

### Limitations

- curated public mini-slice derived from arXiv metadata; not an official benchmark result
- single bounded claim only; not a full paper reproduction
- local deterministic optimizer ablation; no external judge or official scorer
- local proof is not an official benchmark result

## fasttext-ag-news-full-reproduction-20260517

- description: fastText AG News full-data core-track reproduction and bounded improvement proof
- proof_archive: `docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/proof-archive.json`
- artifact_index: `docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/artifact-index.json`
- publication_guard: `docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/publication/proof-publication.json`
- status: `archivable`
- publication_status: `publishable_with_limitations`
- benchmark_name: `full_reproduction_fasttext`
- run_mode: `local_full_ag_news_fasttext`
- judge_type: `operator_artifact_review`
- metric: `accuracy`
- official_scores_claimed: `false`

### Allowed Public Claims

- full AG News fastText core-track baseline, bounded client proposal improvement, and review artifacts are available
- downloadable sanitized release proof bundle and checksum are available

### Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance
- arbitrary paper reproduction or automatic guaranteed improvement

### Artifact SHA256 Summary

- `release_manifest` `artifacts/release-proof-manifest.json` sha256: `7c852ac2024670ff9f96add559b6e217e36209ff4a6acca420538f390a2850b4`
- `release_review_checklist` `artifacts/release-review-checklist.md` sha256: `e558ff9e9e2ff72b2d64c5cf0d81e762064cdd2c5df7f125dfe3807312fdf2c7`
- `release_download_bundle` `artifacts/release-proof-bundle.tar.gz` sha256: `7ff235f7f8293dda4f88c9f02e18871c76bb7a6d43a1a334f276486b7d3afb77`
- `release_download_checksum` `artifacts/release-proof-bundle.sha256` sha256: `2faeaa0cfc4f317dae7c559130af2983d0e6d736b92a3d4bd7e10cfca8719b31`
- `multi_round_report` `artifacts/multi-round-report.json` sha256: `5a808e113e82a52bb3b3f2cf7782ac6f3b5eb5a8965aafef5de099b05a60fe4c`

### Limitations

- full AG News fastText core experiment track only; not all paper tables
- local proof bundle with human review; not an official leaderboard score
- client proposal improvement is bounded to allowlisted fastText parameters
- automatic improvement is not guaranteed beyond the archived run
- local proof is not an official benchmark result

## smol-worldcup-round-004-dev-formal-rescore-20260520

- description: Smol AI WorldCup round-004 dev formal scorer-v2 rescore proof
- proof_archive: `docs/evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/proof-archive.json`
- artifact_index: `docs/evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/artifact-index.json`
- publication_guard: `docs/evidence/proof-archives/smol-worldcup-round-004-dev-formal-rescore-20260520/publication/proof-publication.json`
- status: `archivable`
- publication_status: `publishable_with_limitations`
- benchmark_name: `smol_worldcup`
- run_mode: `local_formal_scorer_v2_rescore`
- judge_type: `local_scorer_v2_with_preserved_llm_judge`
- metric: `SHIFT`
- official_scores_claimed: `false`

### Allowed Public Claims

- debug proof-run artifacts are available
- commands, config, environment, logs, reports, and limitations are published

### Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance

### Artifact SHA256 Summary

- `command_lines` `artifacts/command-lines.md` sha256: `53fc6d029e70f32152529cea382310136c0076d1d5b34fabde784e30defc8833`
- `resolved_config` `artifacts/resolved-config.json` sha256: `30f450bc1727c25ff9ded70657d8f6dfc8f6bc6857cd2a46ff92366d044eb302`
- `environment_manifest` `artifacts/environment-manifest.json` sha256: `69ad9d80b5cbfb766796e3c48820fcfeabaf9adf7a25852ba15f8db393edfa8a`
- `raw_logs` `artifacts/raw-logs.md` sha256: `9293c6b9affe2345f5bc75c6f0891c463a9627e1e3678c90689dcdcf2ed72c9c`
- `raw_reports` `artifacts/raw-reports/smol-worldcup-rescore-report.json` sha256: `d647c577e3e8cda89f92e58345435f4863a512de302a3967605b34fff6f0d5d1`
- `limitations_note` `artifacts/limitations-note.md` sha256: `69bf07f78ee4401487ce3c0e2a67fabff0acf8357dcd7e311080189b88de61a8`
- `confidence_calibration_audit` `artifacts/rescore-artifacts/confidence-calibration-audit.json` sha256: `1f76778288bce9b2c87118c32fc876abbfcc2a6cc3a4b672ed2ada8a233b6642`
- `failure_cases` `artifacts/rescore-artifacts/failure-cases.json` sha256: `4fefd6f23dc6ac6579e7a7f4889e22d7a1ea9023893950d8fad1f0e58be9667b`
- `prediction_jsonl` `artifacts/rescore-artifacts/prediction.jsonl` sha256: `e2a6799d729fec22996a1627b7013a9d24f07ebdc976e8fa70556acfa9b7bca7`
- `score_breakdown` `artifacts/rescore-artifacts/score-breakdown.json` sha256: `0e4dd5930fdefa75285882be4e4cc72023bdeae0fe435a42ba20d0309e0252d6`
- `source_model_eval_report` `artifacts/source-artifacts/source-model-eval-report.json` sha256: `40cc5762f252954dfb8c87777107fb218c93f9da5a6f34403622caf2be2282f6`
- `source_prediction_jsonl` `artifacts/source-artifacts/source-prediction.jsonl` sha256: `fb517422402fb775631917f9a49ccfe1837e64391663a4dce6f7a634eb5677d7`

### Limitations

- formal scorer-v2 rescore 是已有 prediction.jsonl 的本地评分适配器审计。
- 该 proof archive 不包含 Hugging Face submission、leaderboard 成绩或 hidden-test 成绩。
- scorer-v2 口径修正不能宣传为新的模型输出或新的模型能力提升。
- llm_judge 行默认保留原 rubric judge 分数，仍存在 judge independence 风险。
- local proof is not an official benchmark result

## smol-worldcup-round-004-canary-formal-rescore-20260520

- description: Smol AI WorldCup round-004 canary formal scorer-v2 rescore proof
- proof_archive: `docs/evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/proof-archive.json`
- artifact_index: `docs/evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/artifact-index.json`
- publication_guard: `docs/evidence/proof-archives/smol-worldcup-round-004-canary-formal-rescore-20260520/publication/proof-publication.json`
- status: `archivable`
- publication_status: `publishable_with_limitations`
- benchmark_name: `smol_worldcup`
- run_mode: `local_formal_scorer_v2_rescore`
- judge_type: `local_scorer_v2_with_preserved_llm_judge`
- metric: `SHIFT`
- official_scores_claimed: `false`

### Allowed Public Claims

- debug proof-run artifacts are available
- commands, config, environment, logs, reports, and limitations are published

### Blocked Public Claims

- official leaderboard score
- deterministic local fixture score as official benchmark performance

### Artifact SHA256 Summary

- `command_lines` `artifacts/command-lines.md` sha256: `95253c845c487e270066018e2d03bd19b40d27a792aed498611984294987b523`
- `resolved_config` `artifacts/resolved-config.json` sha256: `a41f4295f03c10b2c53a65b1cdc11edea67e9666468b12cd64d37b384cdadc4f`
- `environment_manifest` `artifacts/environment-manifest.json` sha256: `62e42d939c5dd1f564398a4a1f1677719d2796f2b0ed300a0ad406da3a08abe4`
- `raw_logs` `artifacts/raw-logs.md` sha256: `9293c6b9affe2345f5bc75c6f0891c463a9627e1e3678c90689dcdcf2ed72c9c`
- `raw_reports` `artifacts/raw-reports/smol-worldcup-rescore-report.json` sha256: `1d43caa4ad81354372b4f8adfbac81c39b684a55fc9643eda4383143e828b604`
- `limitations_note` `artifacts/limitations-note.md` sha256: `69bf07f78ee4401487ce3c0e2a67fabff0acf8357dcd7e311080189b88de61a8`
- `confidence_calibration_audit` `artifacts/rescore-artifacts/confidence-calibration-audit.json` sha256: `4cd2aaa1811c928d378278ff15177f31386cee423dc96a750ba2365b1504d5e5`
- `failure_cases` `artifacts/rescore-artifacts/failure-cases.json` sha256: `e106f6c7e9c733f848f9c653df217abd700cfc7407966f5026bd23adb0d62c4d`
- `prediction_jsonl` `artifacts/rescore-artifacts/prediction.jsonl` sha256: `be89abf9d90c63d35889f7ec83d2cb46935e9fbe8e5c4652aa7b5934c2679c73`
- `score_breakdown` `artifacts/rescore-artifacts/score-breakdown.json` sha256: `91d7071ec56c1092acc001ddc4a214851d7594ddf8eab92f30033c11276649f0`
- `source_model_eval_report` `artifacts/source-artifacts/source-model-eval-report.json` sha256: `8063fe50a51386112780931bc4407fea961edba579a658dcbe8480b246d9725e`
- `source_prediction_jsonl` `artifacts/source-artifacts/source-prediction.jsonl` sha256: `d842fcb806d4c62b9d0fd38e53a5b5fe6caf8b8947b96f5a00d06381c063f1e5`

### Limitations

- formal scorer-v2 rescore 是已有 prediction.jsonl 的本地评分适配器审计。
- 该 proof archive 不包含 Hugging Face submission、leaderboard 成绩或 hidden-test 成绩。
- scorer-v2 口径修正不能宣传为新的模型输出或新的模型能力提升。
- llm_judge 行默认保留原 rubric judge 分数，仍存在 judge independence 风险。
- local proof is not an official benchmark result

## Global Limitations

- curated public mini-slice derived from arXiv metadata; not an official benchmark result
- single bounded claim only; not a full paper reproduction
- local deterministic routing heuristic; no external judge or official scorer
- local proof is not an official benchmark result
- local deterministic optimizer ablation; no external judge or official scorer
- full AG News fastText core experiment track only; not all paper tables
- local proof bundle with human review; not an official leaderboard score
- client proposal improvement is bounded to allowlisted fastText parameters
- automatic improvement is not guaranteed beyond the archived run
- formal scorer-v2 rescore 是已有 prediction.jsonl 的本地评分适配器审计。
- 该 proof archive 不包含 Hugging Face submission、leaderboard 成绩或 hidden-test 成绩。
- scorer-v2 口径修正不能宣传为新的模型输出或新的模型能力提升。
- llm_judge 行默认保留原 rubric judge 分数，仍存在 judge independence 风险。
