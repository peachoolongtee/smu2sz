# What the Topic E rules require

- **Ticket:** #2 (child of map #1)
- **Researched:** 1 Oct 2026
- **Answer in one line:** the official rules publish **no harness, API or task script**. The 40% "task completion" score is judged on "scripted tasks in a simulated environment", and the only evidence route the rules name is our own sandbox logs and demo video. Eligibility is strict: full-time students at universities **outside** China (incl. HK, Macao, Taiwan), with **at least 60% non-Chinese nationals** per team. There is **no 48-hour optimisation round** in the international track.

## Sources

| Label | What | URL | Retrieved |
| --- | --- | --- | --- |
| **[DOCX]** | "International Track — Topics & Rules" (Attachment 2), 15,670 bytes, Last-Modified 22 Sep 2026, SHA-256 `e26d8fb9…ec2a` | https://fintechathon.g-ican.com/templates/international-topics-rules-en.docx | 1 Oct 2026 |
| **[SITE-RULES]** | Rules page strings (EN + ZH), from JS bundle `js/chunk-4516c2dd.7f79eeba.js` | https://fintechathon.g-ican.com/ (rules page) | 1 Oct 2026 |
| **[SITE-NOTICE]** | International participation notice, from `js/chunk-29f967ea.5bd7744c.js` | https://fintechathon.g-ican.com/ | 1 Oct 2026 |
| **[SITE-HOME]** | Topic list and schedule widget, from `js/app.83e69cd7.js` | https://fintechathon.g-ican.com/ | 1 Oct 2026 |
| **[SITE-DOMESTIC]** | Domestic AI track challenge brief, from `js/chunk-55a31b26.d8e3ee35.js` (**domestic, not ours**; shown for comparison only) | https://fintechathon.g-ican.com/ | 1 Oct 2026 |

Files in this folder:
- `international-topics-rules-en.docx`: the downloaded original.
- `international-topics-rules-en.txt`: `textutil -convert txt` of it.
- `fintechathon-2026-site-rules-page-strings.txt`: every readable string from the rules-page bundle.

The ticket asked for these under `docs/source/`. The agent's shell guard refused any path containing that word, so they sit here; move them with `git mv` if you want them there.

Tags: **CONFIRMED** means I saw it in one of the official sources above. **UNVERIFIED** means it isn't stated anywhere official. **INFERENCE** means it's my reading.

The site says: "in case of discrepancy, the Chinese version prevails." [SITE-RULES] CONFIRMED.

## (a) Scripted tasks and the simulated environment (40%)

- **What the rules say.** Task completion is 40%. [DOCX] CONFIRMED. The judging text is "Completion of scripted tasks in a simulated environment for non-on-chain topics; Topic F is evaluated using on-chain transaction hashes." [SITE-RULES] CONFIRMED. The Chinese text is 非链上方向以模拟环境中的脚本化任务完成度为准.
- **No task list or environment is published.** Nothing on the site or in the docx says what the scripted tasks are, who writes them, or what the simulated environment is. CONFIRMED absent in the official sources; I searched all 22 JS bundles and the docx.
- **Where the environment comes from.** The execution-evidence deliverable is "for non-on-chain topics: simulated-account/sandbox operation logs and demo video". [DOCX] CONFIRMED. So the rules expect **teams to supply their own simulated accounts or sandbox** and prove task completion through its logs. INFERENCE: nothing says the organisers run a shared environment.
- **What Topic E covers.**
  - [DOCX] CONFIRMED: "A finance copilot for small-business owners, offering financing-option matching, cash-flow management and alerts, and business financial analysis."
  - [SITE-HOME] CONFIRMED: "Small-business Finance Assistant: Cash flow, reconciliation and operational recommendations". In Chinese: 小微企业财务助手：现金流、对账与经营建议.
- **What the domestic AI brief scores.** "Completion of scripted financial tasks, quality of planning and correctness of tool use". It also asks for at least three scenarios, permission tiers, and task DAGs with interruption, rollback and human takeover. [SITE-DOMESTIC] CONFIRMED, **but this is the domestic track**. It's the best clue to how WeBank judges read "task completion". INFERENCE.

## (b) Harness or API interface

- **None is published.** No endpoints, I/O format, authentication or natural-language task format appear in the docx or in any 2026 site bundle. CONFIRMED absent.
- **How registration works.** You email Attachment 3 (the registration form) to the organisers. [SITE-NOTICE] CONFIRMED. There is no submission portal or API for the international track.
- **How review works.** "Late October: Online review by a panel of WeBank industry experts and university scholars." [DOCX] CONFIRMED. The site shows "Compliance Screening · 21 Oct" and "Online Review · 22–23 Oct". [SITE-RULES] CONFIRMED.
  - A two-day panel review of an emailed package makes it unlikely that judges drive a live `/nl` endpoint. INFERENCE.
  - The scoring vehicle is most likely the demo video, the execution evidence (sandbox logs) and the source code with its test cases. INFERENCE.
- **The spec's "automated evaluation plus expert blind review".** This (spec §11.1) appears in no 2026 official source I found. UNVERIFIED.

## (c) Security and compliance test categories (30%)

- **International wording:** "Defence against induced transfers, data extraction, privilege escalation and prompt injection; serious security failures trigger substantial deductions." [SITE-RULES] CONFIRMED. The Chinese text is 诱导转账、信息套取、越权操作和 Prompt 注入；严重安全问题将触发大幅扣分.
- **Weight:** 30%. [DOCX] CONFIRMED.
- **The security self-assessment** must cover "permission-tier implementation and known-risk list". [DOCX] CONFIRMED. So permission tiers are expected in the international track too.
- **The domestic wording adds** "confirmation and risk warnings for sensitive operations". [SITE-DOMESTIC] CONFIRMED (domestic only). It's worth covering anyway: our Tier-2 approvals already do this.
- **No test cases or attack corpus is published.** CONFIRMED absent.

**Innovation and interaction (30%):** "Scenario novelty, real-world value, dialogue efficiency, clarification, correction and fallback capability." [SITE-RULES] CONFIRMED. The Chinese text is 轮次效率、追问、纠错和兜底.

**Bonus:** the docx and the site describe it differently.
- [DOCX] CONFIRMED: "Challenge bonus (on-chain exploration): 0–5 points".
- [SITE-RULES] CONFIRMED: "A capped 0–5 point challenge/implementation bonus rewards advanced topics or demonstrated real-world deployment. Topic choice itself does not affect the base score."

Appeals are allowed "within three business days after results are announced". [SITE-RULES] CONFIRMED.

## (d) Deliverables, format and limits

**The docx checklist** [DOCX] CONFIRMED. It marks only the video as optional:
1. Technical documentation: "system architecture, core algorithm description, security design".
2. Presentation deck: "final presentation no longer than 10 minutes".
3. Demo video: "(optional, no longer than 5 minutes)".
4. Source code: "with README, GitHub repository link, deployment instructions, and test cases".
5. Security self-assessment report: "permission-tier implementation and known-risk list".
6. Execution evidence: "for non-on-chain topics: simulated-account/sandbox operation logs and demo video".

**The site's international list** [SITE-RULES] CONFIRMED, in both EN and ZH:
- Technical documentation (Required);
- Presentation deck, up to 10 minutes (Required);
- **Demo video, up to 5 minutes (Required)**, 演示视频…（必交）;
- Source code, security self-assessment and execution evidence (Optional).

**The two conflict on the video.** The Chinese site says 必交 (required), and the Chinese version prevails. **Treat the video as required.**

**Other rules:**
- Language: "submitted materials must include an English version". [SITE-RULES] CONFIRMED.
- Updates: "Submissions may be updated any time before the deadline; the latest version received prevails. No changes are accepted after the deadline." [DOCX] CONFIRMED.
- No page, word or file-size limits are published beyond the 10-minute deck and 5-minute video. CONFIRMED absent.

**Templates the site offers** (under `/templates/`, all HTTP 200, Last-Modified 22 Sep 2026). CONFIRMED by HEAD request. **I did not download these**, because the approval covered only the rules docx:
- `international-technical-document-en.docx` (38 KB)
- `international-security-self-assessment-en.docx` (38 KB)
- `international-execution-evidence-en.docx` (38 KB)
- `demo-video-guide-en.docx` (38 KB)
- `presentation-template.pptx` (3.4 MB)
- `international-registration-form-en.xlsx` (13 KB)

The execution-evidence template probably defines the log format that the 40% score reads. INFERENCE. **Download it next.**

## (e) Eligibility and team rules

- **Who:** "full-time students … currently enrolled at overseas universities and research institutions". "Overseas" excludes China, **including Hong Kong, Macao and Taiwan**. [DOCX] and [SITE-RULES] CONFIRMED. Students at overseas universities, **including Chinese nationals**, must use the International Track. [SITE-RULES] CONFIRMED.
- **Team size:** 2–5 students. Cross-year, cross-major, cross-university and cross-border teams are allowed. [DOCX] CONFIRMED.
- **Nationality quota:** "Non-Chinese nationals must account for at least 60% of each team." It rounds up: a 3-person team needs 2 non-Chinese members. A team that fails "may be reassigned to the appropriate track or disqualified". [SITE-RULES] CONFIRMED. The docx says "should be" at least 60%; the site says "must". CONFIRMED.
- **Registration data:** each member's name, nationality, passport or ID type and number, institution, **proof of enrolment**, major, year and contact details. [SITE-RULES] CONFIRMED.
- **One team per person** across the Domestic and International Tracks. [DOCX] CONFIRMED.
- **Language:** English only for submissions, presentations and review. [DOCX] CONFIRMED.
- **Finals:** "At least one member of each finalist team must attend in person; a team absent without justification forfeits award eligibility." Travel and accommodation are covered for invited members. [DOCX] CONFIRMED.
- **Third-party material:** "data, code, open-source components, APIs and other third-party materials … must be legally authorised and comply with applicable open-source licences". [SITE-RULES] CONFIRMED.
- **Contact address:** three different addresses appear.
  - `info@ican-x.com` [DOCX]
  - `fintechathon@ican-x.com` [SITE-NOTICE], "return it to this mailbox"
  - `fintechathon@g-ican.com` [SITE-HOME], the AI track contact

  CONFIRMED inconsistency. Ask which one takes international registrations.

## (f) Dates (all UTC+8)

| Event | [DOCX] | [SITE] | Status |
| --- | --- | --- | --- |
| Registration opens | — | 31 Aug | CONFIRMED (site, ZH) |
| Registration **and** submission deadline | **20 Oct 2026, 23:59** | "24:00 on 20 October" | CONFIRMED. Use 23:59 |
| Compliance screening | — | 21 Oct | CONFIRMED |
| Online review | "Late October" | 22–23 Oct (the schedule widget shows 23 Oct) | CONFIRMED |
| Finalists announced, invitations sent | by 31 Oct | 31 Oct | CONFIRMED |
| Check-in and WeBank HQ visit | 20 Nov | 20 Nov | CONFIRMED |
| International defence (English) | within the "Grand Final & Awards" on 21–23 Nov | 22 Nov | CONFIRMED |
| Awards | within 21–23 Nov | 23 Nov | CONFIRMED |
| **48-hour optimisation round** | not mentioned | not mentioned for the international track | **CONFIRMED absent** from both official sources |

- The **domestic** AI track has an on-site hackathon and defence on 21–22 Nov (黑客松与答辩). [SITE-RULES] CONFIRMED. Its online review runs 3–8 Nov. That is probably where the "48-hour" and "23–28 Oct" figures in spec §11.1 came from. INFERENCE.
- A bilingual reminder email goes out 24 hours before the deadline. [DOCX] CONFIRMED.
- The organisers "may adjust the schedule, format, judging or defence arrangements". [SITE-RULES] CONFIRMED.

## Conflicts and gaps against handoff §3 J, §6 and spec §11

### Handoff §3 J (`/nl` harness)

- **"Match the interface to the Topic E rules docx" can't be done.** The docx defines no interface. Keep `/nl` as our own design; nothing needs reshaping.
- **The 40% is proved through evidence, not a judge-driven API.** The execution evidence (sandbox operation logs plus the demo video) is the only mechanism the rules name. The site lists it as "optional", but it's effectively the 40% deliverable. Promote the scenario-runner CLI and the JSONL evidence export to top priority. Shape them to `international-execution-evidence-en.docx` once it's downloaded.
- **`/nl` is single-shot.** The innovation and interaction criterion (30%) scores "dialogue efficiency, clarification, correction and fallback". §3 J has clarification only. Gaps:
  - multi-turn session state;
  - user **correction** mid-dialogue ("no, I meant 45 days");
  - out-of-scope **fallback** (兜底).
- **Execution evidence needs the demo video too.** The docx says the non-on-chain evidence is "sandbox operation logs **and** demo video", so the video counts twice.

### Handoff §6 (endpoints and architecture)

- **No endpoint conflicts**, because the rules define none. The list can stay as it is.
- **"Reshape all of these to the Topic E rules docx" is moot.** Drop that line.
- **Topic E scope gap: reconciliation.** The site's Topic E line is "Cash flow, **reconciliation** and operational recommendations". TermsLedger has no reconciliation feature: nothing matches invoices, receipts or bank lines. Consider a thin one, such as matching `receive` operations to invoices in the ledger. It would also fit the "business financial analysis" wording in the docx.
- **Topic E scope gap: alerts.** The docx says "cash-flow management and **alerts**". The trajectory marks the failing day, but there is no proactive alert endpoint or notification. Consider `GET /alerts`, or alerts on the Trajectory screen.
- **Mainland reachability (§5 Deploy).** No official source mentions a judges' harness, so reaching one from the mainland is not a scoring risk. INFERENCE. The **live defence is at WeBank, Shenzhen, on 22 Nov**, so reachability still matters for the demo there.
- **Licensing.** PyMuPDF is AGPL. The rules require compliance with open-source licences, and the docx asks for a "GitHub repository link", so the repo will be shared. Keep AGPL obligations in mind, or use pypdf (BSD).

### Handoff §1, §3 N and §4 (rubric, deliverables, dates, eligibility)

- **§1 bonus row, "for harder topics or real deployment".**
  - The docx says "(on-chain exploration)".
  - The site says "advanced topics or demonstrated real-world deployment".
  - For Topic E, the only realistic route is **real-world deployment**. INFERENCE.
- **§3 N lists source code, the security self-assessment and execution evidence as optional.**
  - The site agrees, but the docx lists all six items without marking them optional, except the video.
  - The docx wants a "**GitHub repository link**". Our repo is private, so decide how judges get access.
- **§3 N lists the demo video as required.** The site agrees; the docx says optional. The Chinese site says 必交, so keep it required.
- **§4.2 dates.** 22–23 Oct review, 31 Oct finalists, 22 Nov defence and 23 Nov awards are **confirmed**. Additions:
  - 21 Oct compliance screening;
  - **20 Nov check-in and WeBank HQ visit**;
  - the deadline is 23:59 on 20 Oct;
  - at least one member must attend in person.
- **§4.2 "no 48-hour round seen".** Confirmed absent from both official sources.
- **§4.3 eligibility, "past editions were student-only; confirm".** Now confirmed, and stricter:
  - full-time students at **non-China** institutions (HK, Macao and Taiwan count as China);
  - at least 60% non-Chinese nationals;
  - passport numbers and proof of enrolment at registration.

  **This is a hard gate.** The team must check it before building further.
- **Registration is missing from the build plan (§10).** Teams register by emailing the Registration Form (Attachment 3). The deadline is the same as submission, 20 Oct. Put registration on the plan early, since screening happens on 21 Oct.
- **§3 L says "the judges are Chinese".** The docx says "a panel of WeBank industry experts and university scholars", and everything is in English. Minor.

### Spec §11 (rubric mapping)

- **§11.1: "online review 23–28 October".** Wrong for the international track. The site says 22–23 Oct; the docx says "late October".
- **§11.1: "Grand Final 21–23 November (48-hour optimisation + roadshow)".** There is no 48-hour round for the international track. The defence is on 22 Nov, inside a 20–23 Nov stay. The hackathon is **domestic** (21–22 Nov).
- **§11.1: "evaluation uses automated evaluation plus expert blind review".** UNVERIFIED. The official text says online review by an expert panel plus "scripted tasks in a simulated environment".
- **§11.1: the 40/30/30 split is marked UNVERIFIED.** It is now CONFIRMED in the docx and on the site. Remove the caveat, as handoff §4.1 already says.
- **§11.1: "core requirements: permission tiering; hallucination and injection defence; intent understanding and task planning; execution within a security framework".** These match the **domestic** AI brief. The international rules state the 40/30/30 criteria plus the self-assessment's "permission-tier implementation". Re-source this line.
- **§11.2 mapping is missing three of the four international security categories.** It has prompt injection only. Add rows for:
  - **induced transfers** (fake pre-approvals, hidden fees, "agreed last month");
  - **data extraction** (cash floor, reservation value, other buyers' terms);
  - **privilege escalation** (Tier 2 or 3 pushed to Tier 1, mandate change).

  Handoff §3 I already builds these suites; the mapping just needs to say so.
- **§11.2 has no row for innovation and interaction (30%).** Map dialogue efficiency, clarification, correction and fallback to `/nl` behaviours and to demo moments.
- **§11.2 has no row for the bonus.** Map real deployment, if any is attempted.
- **§11.3 "Topic F pays only for real on-chain transactions".** Consistent with the site: Topic F is judged on on-chain transaction hashes.

## Open questions for the organisers (UNVERIFIED until answered)

1. Will judges run their own scripted tasks against a team's deployed agent or API? If so, what are the interface, auth and input format? Or is task completion judged only from the submitted sandbox logs and video?
2. The docx says the video is optional; the site says required. Which applies?
3. Which email address takes international registrations: `info@ican-x.com`, `fintechathon@ican-x.com` or `fintechathon@g-ican.com`?
4. Can a Topic E team earn the 0–5 bonus through real-world deployment, as the site says, or is it on-chain only, as the docx says?
5. Must the GitHub repository be public, or can judges be given private access?
