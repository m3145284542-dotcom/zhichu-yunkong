# Phase 13.0B-HF1 — Evidence Registry Integrity Repair

## Status

PASS candidate. This hotfix repairs only the Phase 13.0B artifact-hash contract and does not change scientific evidence or presentation selection.

## Original issue

`outputs/phase13_0b/phase13_0b_summary.json` registered `scripts/build_phase13_0b.py` as `0cb439653d1590e305a5a0bdce7c172f28abc0d02e32c66b26ad20644621fd47`, while a raw Windows checkout hash reported `142efd3c9545477459b138b135ce2522505d58ae01744d4a874d46a8e77e0706`.

## Historical root cause

The script bytes committed in both `5defef8` and the hotfix starting HEAD `cc394978a4481f8527092aaaa720e7740d5a6e28` hash to `0cb439653d1590e305a5a0bdce7c172f28abc0d02e32c66b26ad20644621fd47`. There is no script diff between those commits. The apparent mismatch was caused by Git's Windows checkout conversion from committed LF newlines to CRLF (`core.autocrlf=true`), not by Phase 13.1 or a later merge.

The original registry mixed byte domains: the script entry reflected committed LF bytes, while the other seven generated text entries reflected CRLF working-tree bytes before Git normalization. The registry does not include its own summary file, so there is no self-referential hash cycle.

## Repair

The builder now registers the SHA-256 of each Phase 13.0B text artifact after deterministic LF newline normalization. This equals the final Git committed bytes and is independent of checkout newline conversion. It also asserts the complete eight-entry registry before writing the summary and records zero Phase 13.0B artifact drift in validation metadata.

Because the builder itself changed to implement the repair, its corrected registered hash is `732ded96fbc9cd43b36b94e80854bd765a2822bd91e5618972593048e885118a`. The original registered hash was `0cb439653d1590e305a5a0bdce7c172f28abc0d02e32c66b26ad20644621fd47`; the raw CRLF checkout hash `142efd3c9545477459b138b135ce2522505d58ae01744d4a874d46a8e77e0706` is not used because it is machine-dependent.

## Unchanged content

No algorithm, model, prediction, optimization result, statistical result, claim, evidence shortlist, figure shortlist, presentation recommendation, claim–evidence relationship, canonical source selection, rejected claim, prohibited wording, or caveat changed. No experiment, statistical test, result regeneration, visual asset, architecture diagram, or PPT was produced.

## Integrity verification

- Frozen baseline and Phase 13.0B commit ancestry: PASS.
- Phase 7/8/9/9.1 registered canonical artifacts: 76/76 PASS; drift 0.
- Phase 13.0A registered sources: 88/88 PASS; drift 0.
- Phase 13.0B registered files under the corrected committed-byte contract: 8/8 PASS; drift 0.
- Pre/post structured semantic digests for claims, metric shortlist, figure shortlist, slide evidence map, limitations registry, and DOEF pipeline specification: identical.
- Phase 13.1 may be restarted after this hotfix is committed and the post-commit audit passes.

