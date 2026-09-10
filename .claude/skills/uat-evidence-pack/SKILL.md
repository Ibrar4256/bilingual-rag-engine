---
name: uat-evidence-pack
description: Capture UAT evidence artifacts for one or more completed requirements, in the exact format Client_UAT_Evidence_README.md specifies, and update SPEC.md's traceability table. Use after finishing a phase of implementation, before marking any requirement "Done".
---

# UAT Evidence Pack

The client's evidence format is fixed by `docs/Client_UAT_Evidence_README.md` — do not invent a different format (e.g. a custom test report). Every artifact must be either:
- a timestamped log excerpt containing the specific `EVIDENCE_*` marker named for that AC in the README, or
- a DB query snippet (the exact query + output rows), or
- a request/response payload pair from a live endpoint call.

## Steps

1. Identify which requirement(s)/AC(s) just landed, from `SPEC.md` §5.
2. For each, find the matching AC in `docs/Client_UAT_Evidence_README.md` §4 and note its expected log marker(s) or DB proof query.
3. Run the actual system to produce that evidence:
   - For hash-skip/atomic-swap/dual-path proof: run the relevant `bilingual_etl.scripts.*` entrypoint and grep `logs/runtime.log` for the named marker.
   - For dual-path/protected-terms proof: run the DB proof query from the README against the local Postgres instance.
   - For API proof: call the live endpoint (e.g. via `curl` or `httpx`) and capture request + response JSON.
4. Save each artifact under `uat-evidence/<requirement-id>/` (e.g. `uat-evidence/R10-hash-gate/rerun.log`, `uat-evidence/R9-dual-path/query_output.txt`) — create this convention consistently since the README doesn't dictate folder naming itself.
5. Update `SPEC.md` §5's traceability table: fill in the "UAT Evidence Artifact" column with the path, and set "Status" to "Done" only once the artifact exists and matches the required format.
6. If a required log marker never appears (feature not actually emitting it), do not mark the requirement done — report the gap instead of fabricating or approximating the evidence.
