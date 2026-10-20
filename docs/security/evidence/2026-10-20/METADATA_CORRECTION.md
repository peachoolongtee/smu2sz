# Metadata correction, 20 Oct 2026 (about 09:00 UTC)

The manifest generator (`scripts/security_manifest.py`) writes the release gate's fixed description of build, scope and
configuration into every folder it seals, including `LLM_MODE: cache (no model provider is called)`. For three folders that
description was wrong: they record live DeepSeek runs and checks of the hosted judges' demo. A review of the submitted
documents found the contradiction between those manifests and the folders' own summaries.

Each of the three `MANIFEST.json` files now describes its own runs: the machine that ran the checks, the deployed server and
its configuration, the mode observed, the assessment window and the exclusions, with a `metadata_correction` field. No
result file was changed. In `judges-demo-live-78b211f0/summary.txt` the quoted id of the live folder was updated. Each folder
was then resealed, so its evidence id (the sha256 of its `SHA256SUMS`) changed:

| Folder | Former id | Id after the correction |
| --- | --- | --- |
| `live-78b211f0/` | `sha256:ec02a982b50aa427` | `sha256:1cf8bf8d9daa79d8` |
| `judges-demo-live-78b211f0/` | `sha256:92e71fd3759897c3` | `sha256:2135d88158086ce4` |
| `judges-demo-checks-78b211f0/` | `sha256:8e17f33e72969b11` | `sha256:95f3b4f46a7d9eba` |

The release gate's folder `int-78b211f0/` (`sha256:6f665b8ae82df362`) was not changed: its manifest describes its own runs,
and it stays as sealed at gate time. Its `summary.txt` quotes the live folder's former id, `sha256:ec02a982b50aa427`.

Check any folder with `sha256sum -c SHA256SUMS` inside it; the id is `sha256sum SHA256SUMS`, first 16 hex digits.
