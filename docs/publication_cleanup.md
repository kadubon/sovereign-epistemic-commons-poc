# Publication Cleanup Note

## Scope

This note records a lightweight publication-cleanup pass performed after the v2 experiments were already complete.

No heavy experiment reruns were performed.
No new scientific claims were introduced.
The goal was repository hygiene, safer scientific wording, and clearer bookkeeping.

## What Was Cleaned Up

- added `run_uid` as the canonical globally unique run identifier in metrics CSVs and manifest files
- preserved `run_id` as a legacy short identifier for compatibility
- patched existing result tables and manifests in place using postprocessing only
- corrected legacy v1 manifest paths so they point to the current `results/v1_exploratory/` and `logs/v1_exploratory/` locations
- updated README and summary text to reduce overclaim risk
- clarified that Gemma runs are auxiliary backend sanity checks, not primary scientific evidence

## What Was Not Done

- no heavy reruns of the scripted confirmatory matrix
- no redesign of the simulator or governance logic
- no changes to the scientific scope of the PoC

## Transparency Note

`run_uid` is guaranteed in patched metrics CSVs and manifests.
Existing raw JSONL logs may still contain only the legacy `run_id`.

This cleanup should be read as a publication-safety pass, not as a new experiment phase.
