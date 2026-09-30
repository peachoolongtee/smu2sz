# What the official submission templates require

Resolves wayfinder ticket #12. Downloaded 1 Oct 2026, with the owner's approval, from `https://fintechathon.g-ican.com/templates/` (the official site; no mirrors).

**Short answer.** The templates are thin. Each docx is one page: a header table, 3–5 numbered headings, and one-line prompts with "Write here" under each. None sets a page or word limit, a file-size limit or a machine-readable log schema. The execution-evidence template asks for a Word document with three sections. Under "Logs or Transactions" it asks for "Timestamp, action, result and relevant screenshot/link" per entry, then a reproduction guide for judges. Our JSONL export has an action (`kind`) and a coarse result (`status`). It has **no timestamp or day, no result detail, and no link**. It also omits the payload and result JSON, so **a judge cannot recompute `entry_hash`**.

Tags: **CONFIRMED** means I saw it in the template file (or the site bundle, where marked [SITE]). **INFERENCE** means it's my reading.

## Files

All under `docs/research/templates/`. Each original sits beside a `.txt` extraction (python-docx and python-pptx; headings are marked `#`, tables `[TABLE]`). All the originals have Last-Modified 22 Sep 2026 02:43 GMT.

| Template | File | Bytes | SHA-256 (first 12) | Site label, international track [SITE] |
| --- | --- | --- | --- | --- |
| Execution evidence | `international-execution-evidence-en.docx` | 38,077 | `9e25c4c2a477` | DOCX · Optional (可选) |
| Security self-assessment | `international-security-self-assessment-en.docx` | 38,101 | `c74286e20458` | DOCX · Optional (可选) |
| Technical document | `international-technical-document-en.docx` | 38,246 | `92c2affd4be3` | DOCX · Required (必交) |
| Demo-video guide | `demo-video-guide-en.docx` | 38,228 | `cbfc10b3996c` | DOCX · Required (必交) |
| Deck | `presentation-template.pptx` | 3,376,472 | `c7cecdfe3e04` | PPTX · Required (必交) |

The site labels come from `js/chunk-4516c2dd.7f79eeba.js`, fetched again on 1 Oct 2026.

**Also linked, but not downloaded.** The international track also links `templates/source-code-readme-template-en.md` ("Source Code README", MD · Optional; 992 bytes, HTTP 200). It wasn't in the approved list, so I left it. **Approve it next**; it's the only template left. The same bundle now points the international "Registration Form" at `templates/team-information-form.xlsx`, not the `international-registration-form-en.xlsx` that `topic-e-rules.md` lists. CONFIRMED [SITE].

**Common to all four docx templates.** CONFIRMED:
- Title line "2026 FINTECHATHON · SUBMISSION TEMPLATE", then "International AI Track | <name>".
- A header table with three rows to fill in: **Team name, Competition track, Submission date**. The video guide labels them bilingually: 队伍名称 / Team, 参赛赛道 / Track, 提交日期 / Date.
- Numbered headings `01`, `02`, … Each prompt is followed by "Write here".
- Footer: "If a newer template is published, the newer version prevails." **Re-check the site before submitting.**
- No page, word or file-size limits and no font rules. CONFIRMED absent. The only numeric limit anywhere in the templates is the video's five minutes.

## 1. Execution evidence

"Optional supporting material for operation logs or on-chain transaction evidence." CONFIRMED. No language line; the rules say English. The site marks it Optional, but it's our only vehicle for the 40% task-completion score (see `topic-e-rules.md` §a). INFERENCE.

**Sections, in order.** CONFIRMED:
1. **01 Evidence Summary**
   - "Selected topic and scenario"
   - "What the evidence demonstrates"
2. **02 Logs or Transactions**
   - "Simulated account/sandbox logs, or transaction hashes for Topic F"
   - "Timestamp, action, result and relevant screenshot/link"
3. **03 Reproduction Guide**
   - "Steps required for judges to reproduce or verify the evidence"

**Evidence schema.** CONFIRMED: the template defines no machine-readable format. The only per-entry fields it names are:

| Field | Template wording |
| --- | --- |
| timestamp | "Timestamp" |
| action | "action" |
| result | "result" |
| screenshot or link | "relevant screenshot/link" |

- It gives no format for the timestamp (wall-clock or simulated), no column order, and no rule on whether logs are pasted inline or attached. CONFIRMED absent.
- It asks for no hashes for non-on-chain topics; hashes are named only for Topic F. CONFIRMED. Our hash chain is therefore extra credibility, not a requirement. INFERENCE.
- The deliverable is the filled **docx**. A JSONL file is at best an attachment or a repository link cited from section 02. INFERENCE.

**Scoring hints.**
- "for judges to reproduce or verify" (CONFIRMED) means judges are expected to check the evidence themselves, not just read it. Our strongest angle: a one-command replay plus a standalone chain verifier. INFERENCE.

## 2. Security self-assessment

"Optional supporting material. Please complete this document in English." CONFIRMED. The rules docx says it must cover "permission-tier implementation and known-risk list" (`topic-e-rules.md` §c).

**Sections, in order.** CONFIRMED:
1. **01 Permission Model**
   - "Roles, operations and permission boundaries"
   - "Confirmation, verification and rollback mechanisms"
2. **02 Security Tests**
   - "Prompt injection, social engineering, privilege escalation and failure recovery tests"
3. **03 Data and Privacy**
   - "Data provenance, consent, minimisation, storage and deletion"
4. **04 Known Risks**
   - "Risk, impact, mitigation and planned improvement". These are four columns per risk. INFERENCE: a table fits.

**Scoring hints.**
- The test list here differs from the 30% rubric: induced transfers, data extraction, privilege escalation and prompt injection. The template adds **social engineering** and **failure recovery**; the rubric adds **induced transfers** and **data extraction**. CONFIRMED. Cover the union.

## 3. Technical document

"Required material for the International AI Track. Please complete this document in English." CONFIRMED.

**Sections, in order.** CONFIRMED:
1. **01 Project Overview**
   - "Problem, target users and selected topic"
   - "Core value and innovation"
2. **02 System Architecture**
   - "Architecture diagram and component responsibilities"
   - "Models, tools, data sources and external services"
3. **03 Agent Design**
   - "Intent understanding, planning, tool use and state management"
   - "Core algorithms and evaluation approach"
4. **04 Security Design**
   - "Tiered permissions and confirmation for sensitive actions"
   - "Protection against prompt injection, privilege escalation and privacy leakage"
5. **05 Deployment and Testing**
   - "Environment, deployment instructions, test cases and known limitations"

**Scoring hints.**
- "Intent understanding, planning, tool use and state management" echoes the domestic brief's "quality of planning and correctness of tool use". INFERENCE: judges will read the agent-design section against the 40% criterion.

## 4. Demo-video guide

"Required for the International AI Track. The video must be no longer than five minutes." CONFIRMED. This settles the Optional-versus-Required conflict noted in `topic-e-rules.md` §d: it is **required**.

**Sections, in order.** CONFIRMED. The guide is a checklist for the video, not a document to submit (INFERENCE):
1. **01 Recommended Structure**, in this order:
   1. "Project and team introduction"
   2. "End-to-end demonstration of the core scenario"
   3. "Safety mechanisms, innovation and results"
2. **02 Video Quality**
   - "Use 16:9 landscape and preferably 1080p"
   - "Make interface text, narration and English subtitles clearly legible"
3. **03 Final Check**
   - "No copyrighted or sensitive material"
   - "Suggested filename: Track-TeamName-DemoVideo"

**Limits.** CONFIRMED:
- 5 minutes or less;
- 16:9 landscape, 1080p preferred;
- **English subtitles** expected.

No file type, codec or size limit is given. CONFIRMED absent.

## 5. Deck template

`presentation-template.pptx`. It's the same file for the domestic and international tracks [SITE]. CONFIRMED:
- 16:9 widescreen (12,192,000 × 6,858,000 EMU).
- Four slides:
  1. Title slide: placeholders 作品名 (project name) and 团队名 (team name).
  2. Contents slide: "目录 / CONTENTS" with six numbered items, 01–06, each "目录内容".
  3. Content slide: a title placeholder, 演示主标题.
  4. Closing slide: a full-bleed "THANKS 谢谢观看!" image.
- The **2025** FinTechathon logo is baked into the background images: the title and closing images, and the content-slide header band. The file metadata dates it to 18 Sep 2025. **The organisers reused last year's deck.**
- Fonts: HarmonyOS Sans SC Bold and Medium, 宋体, Arial, Calibri.
- No speaker notes (one notes slide holds only "1") and no section guidance.

**Limits.** The 10-minute limit comes from the site, not the template. CONFIRMED. There is no slide-count limit. The six-item contents slide suggests up to six sections. INFERENCE.

## Gaps against our plan

Plan sources:
- `docs/ARCHITECTURE.md`: `GET /evidence` → `LedgerStore.export_evidence`, built by `app/persistence/chain.py::build_evidence`;
- handoff §3 I, J and N;
- `docs/DEMO_FLOW.md`;
- spec v2 §10.3 (the five-minute structure).

**What the export actually emits today** (`build_evidence`):
- One line per operation: `{record:"operation", seq, op_id, kind, idempotency_key, status, prev_hash, entry_hash}`.
- One final line: `{record:"chain", operations, chain_valid, head_hash, genesis_hash}`.
- `entry_hash = sha256(prev_hash + payload_json + result_json)`.

### Execution evidence (highest priority: this carries the 40%)

1. **No timestamp.** The template asks for "Timestamp" per entry; our lines have none.
   - The op payload already carries `day` (simulated day) and the DB records `exported_at`, but neither reaches the export.
   - **Change:** add `day` (simulated) and `recorded_at` (UTC ISO-8601 wall clock at append) to each operation line. That means adding a `recorded_at` column to `operations`.
   - The column must go into the hashed payload or be listed as unhashed metadata. Decide which in an ADR.
2. **The result is only `status`.** The template asks for the "result". `EXECUTED`, `REFUSED` or `PENDING_APPROVAL` alone doesn't say why.
   - **Change:** export `tier`, `violations[].code` and `message` from `result_json`.
3. **The action is only `kind`.** `DRAW_FACILITY` with no amount, facility or counterparty isn't a readable action.
   - **Change:** export the payload's key fields: `requested_by`, `amount_fen` or the ¥ string, `facility_id` / `offer_id` / `receivable_id`, `source_verdict_id` and `mandate_version`. Simplest is to embed `payload` and `result` in full.
4. **Judges can't verify the hashes.** The export omits `payload_json` and `result_json`, so nobody outside our DB can recompute `entry_hash`, although the reproduction guide asks judges to "reproduce or verify".
   - **Change:** include the canonical `payload_json` and `result_json` strings on each line.
   - Ship `scripts/verify_evidence.py`, standard library only, which recomputes the chain from the JSONL alone.
5. **No screenshot or link per entry.** The template asks for a "relevant screenshot/link".
   - **Change:** have the scenario runner write each step's Playwright screenshot to `evidence/<scenario>/<seq>.png`, and add a `screenshot` path or URL field to each line.
   - At minimum, the docx table links the screen and the video timestamp for each scene.
6. **Security refusals outside the executor are missing.**
   - `security_events` (UNKNOWN_COUNTERPARTY, DATA_EXTRACTION, UNEVIDENCED_CLAIM, …) aren't in the chain or the export, so the FastCapital security scene leaves no evidence line.
   - **Change:** export them as `record:"security_event"` lines with `day`, `kind`, `counterparty_id`, `trace_id` and the span. Either chain them or hash them into the final line.
7. **No scenario or topic header.** Section 01 asks for "Selected topic and scenario" and "What the evidence demonstrates".
   - **Change:** start the JSONL with a `record:"run"` line: topic "E", scenario id (`golden_sme`), fixture hash, mandate version and hash, `LLM_MODE`, git SHA, `started_at`, and the expected verdicts.
   - Also add a `trace_id` or task id per operation, so lines group into scripted tasks. The template doesn't name this field. INFERENCE: it helps "task completion" read per task.
8. **No request text.** The template doesn't require the natural-language request (CONFIRMED absent). Still, add the `/nl` turn text (the request) to the run's task records, so a judge sees request → plan → operation. INFERENCE; nice to have.
9. **The deliverable format is wrong.** The template is a docx with a Team/Track/Date header and three sections; our plan produces JSONL only.
   - **Change:** add a generator or a hand-filled `execution-evidence.docx` covering:
     - 01: Topic E, the three DEMO_FLOW scenes plus the security scene, one line each on what they prove;
     - 02: a table of timestamp | action | result | screenshot/link, rendered from the JSONL, with the full JSONL attached or linked from the repo;
     - 03: the reproduction steps.
10. **No reproduction path yet.** `scripts/demo.py` (the scenario runner) doesn't exist; `DEMO_FLOW.md` assumes it.
    - **Change:** build the runner (handoff §3 J), then document exactly: `docker compose up` (or the local command) → `POST /demo/reset` → `python scripts/demo.py --scenario golden_sme --export evidence.jsonl` → `python scripts/verify_evidence.py evidence.jsonl`. Include the expected `head_hash` for the cache-mode run, since it's deterministic under `LLM_MODE=cache`.
    - Timestamps (item 1) must stay outside the hash, or be simulated, for that `head_hash` to stay stable.

### Security self-assessment (handoff §3 I)

11. **Rollback isn't covered.** The template asks for "Confirmation, verification and rollback mechanisms". The ledger is append-only and `/demo/reset` isn't rollback.
    - **Change:** define and document the compensating operations: repay a draw, expire or cancel a commitment, withdraw an approval request. Also show how a refused or pending operation leaves state untouched.
12. **Failure-recovery tests are missing.** §3 I has no failure-recovery suite; the circuit breaker is P1.
    - **Change:** add tests for an LLM backend error or timeout (→ abstain / NO_VERDICT, nothing booked), a DB write failure mid-execute (no half-applied operation), an idempotent retry after a crash (DUPLICATE), and a broken chain (detected with `chain_valid=false`). Promote the circuit breaker to CORE.
13. **Social engineering needs a name.** The template says "social engineering", so label our induced-transfer, fake pre-approval and "agreed last month" cases as social engineering in the report. No new code.
14. **Data and privacy has no plan.** The template asks for provenance, consent, minimisation, storage and deletion.
    - **Change:** write a section stating:
      - all data is synthetic fixtures (provenance);
      - no real personal data (consent);
      - the model sees only the documents, never the mandate, menu or reservations (minimisation);
      - storage is SQLite locally and Postgres in deploy;
      - deletion is `/demo/reset`;
      - which text is sent to the Anthropic or DeepSeek APIs in live mode, and that cache mode sends none.
15. **Known risks need a table.** Use a four-column table (risk | impact | mitigation | planned improvement), seeded from ARCHITECTURE's trust boundaries and the cut ladder.

### Technical document and deck (handoff §3 N)

16. **§3 N maps no sections.** It lists a "technical document" with no outline.
    - **Change:** adopt the five template headings verbatim, and map:
      - 02 → ARCHITECTURE pipeline and module map, drawn as a **diagram image** (the ASCII block won't do);
      - 02 "Models…" → `claude-sonnet-5-5` / `claude-opus-5-5` / `deepseek-flash` plus the cache backend;
      - 03 → `nl/` sessions (clarification, correction, fallback) and the engine and router algorithms, with E3, E10, E4 and E7 results as the "evaluation approach";
      - 04 → tiers and the executor order;
      - 05 → Docker Compose, the test suites and the known limitations.
17. **The deck needs rebranding.**
    - The official template carries 2025 branding and Chinese placeholders.
    - **Change:** replace 作品名 / 团队名 and 目录内容 with English text, and keep the template's four slide types.
    - Decide whether to accept the baked-in "2025" logo or ask the organisers for a 2026 version. INFERENCE: using the official file as-is is safer than editing its images.
    - Fit the spec v2 §16 arc into at most six contents items.

### Demo video (`DEMO_FLOW.md`, spec v2 §10.3)

18. **There's no team introduction.** The guide's first beat is "Project and team introduction"; spec §10.3 opens with "The asymmetry" and has no team beat.
    - **Change:** add about 10 seconds of team and project intro at 0:00, and trim "The asymmetry" to about 30 seconds.
19. **"Results" have no slot.** The guide's third beat is "Safety mechanisms, innovation and results"; DEMO_FLOW shows no results.
    - **Change:** add a 15–20 second results card, filled from the real runs. These are the targets, not results yet:
      - injection suite: 20 of 20 refused, ¥0 booked;
      - E3: 30 of 30 engine cases exact;
      - wording invariance holds;
      - `chain_valid=true` with the `head_hash`.
    - Also show one clarification or correction turn of `/nl`, since the innovation score names "clarification, correction and fallback".
20. **No subtitles or format plan.** DEMO_FLOW is silent on format.
    - **Change:** record at 1920×1080, 16:9, and burn in English subtitles.
    - Check that the UI's bilingual labels and ¥ figures are legible at 1080p. Increase the chart and verdict font sizes if not.
    - Name the file `International-AI-Track-<TeamName>-DemoVideo.mp4`. The guide says "Track-TeamName-DemoVideo"; the exact track string is INFERENCE.
21. **Five minutes is tight.** DEMO_FLOW has three scenes, capex and the security scene, plus spec §10.3's prior-art close.
    - **Change:** keep capex as a cut of 20 seconds or less, as §10.3 already does, and drop the prior-art slide to the deck if the intro and results beats push past 5:00.
    - Check that the video contains no third-party logos or copyrighted clips (Walmart is named in the pitch; words are fine, logos are not). INFERENCE.

### Open items

- Approve downloading `source-code-readme-template-en.md`. The handoff says to submit the source code, and its README template is still unread.
- Re-download all templates just before 20 Oct, per the footer's "newer version prevails".
