# Submission requirements: FinTechathon 2026, International AI Track, Topic E

- **Team:** ISMOGGER. **Entry:** FLOW (code name TermsLedger).
- **Verified:** 18 Oct 2026, 05:46 to 05:50 UTC, against the official site `https://fintechathon.g-ican.com/` only. No mirrors and no third-party pages.
- **Method.** The site is a JavaScript single-page app. Its HTML shell (3,274 bytes) has no text, and `/templates/` has no index page (HTTP 404). So I read the official JS bundles the shell loads and every template file directly, and compared each with the copies saved in `docs/research/`. Nothing was saved into the repository. Scratch copies stayed outside it.
- **Tags.** **VERIFIED** means seen today in an official source. **VERIFIED (saved)** means seen in an official file that is byte-identical to the saved copy (same MD5 ETag and SHA-256). **ABSENT** means the official sources say nothing about it. **ASSUMED** means it is not in any official source, and the proposed assumption is given.
- **Precedence.** "The Chinese and English notices are published together; in case of discrepancy, the Chinese version prevails" (rules page, international statement). VERIFIED.

## 1. Sources

| Label | What | Where | State on 18 Oct 2026 |
| --- | --- | --- | --- |
| [RULES-DOCX] | "International Track — Topics & Rules" (Attachment 2) | `templates/international-topics-rules-en.docx`; saved as `docs/research/international-topics-rules-en.docx` and `.txt` | 15,670 B, Last-Modified 08 Oct 2026 12:56:11 GMT, ETag `B2519AC6…545D` = MD5 of the saved copy; SHA-256 `e26d8fb9…ec2a`, the same as on 1 Oct. **Unchanged** |
| [SITE-RULES] | Rules page, EN and ZH: process, deliverables, criteria, statement | `js/chunk-4516c2dd.7f79eeba.js`; saved strings in `docs/research/fintechathon-2026-site-rules-page-strings.txt` | Same content-hashed filename as on 1 Oct, 41,226 B, Last-Modified 08 Oct 2026. **Unchanged** (the hash in the filename is the same) |
| [SITE-NOTICE] | International participation notice | `js/chunk-29f967ea.5bd7744c.js` | Same filename as on 1 Oct. **Unchanged** |
| [SITE-HOME] | Home page: topic list, challenge brief, schedule widget | `js/app.83e69cd7.js` | Same filename as on 1 Oct. **Unchanged** |
| [T-TECH] | Technical document template | `templates/international-technical-document-en.docx`; saved under `docs/research/templates/` | 38,246 B, LM 08 Oct 2026, ETag = MD5 of the saved copy, SHA-256 `92c2affd…83c0`. **Unchanged** |
| [T-SEC] | Security self-assessment template | `templates/international-security-self-assessment-en.docx` | 38,101 B, LM 08 Oct, SHA-256 `c74286e2…2903`. **Unchanged** |
| [T-EVID] | Execution evidence template | `templates/international-execution-evidence-en.docx` | 38,077 B, LM 08 Oct, SHA-256 `9e25c4c2…efc5`. **Unchanged** |
| [T-VIDEO] | Demo video guide | `templates/demo-video-guide-en.docx` | 38,228 B, LM 08 Oct, SHA-256 `cbfc10b3…614e`. **Unchanged** |
| [T-DECK] | Presentation template | `templates/presentation-template.pptx` | 3,376,472 B, LM 08 Oct, ETag `7AB918DF…D6F4` = MD5 of the saved copy. **Unchanged** (compared by ETag, not downloaded) |
| [T-README] | Source code README template | `templates/source-code-readme-template-en.md` | 992 B, LM 08 Oct, SHA-256 `72839764…acf7`. **Read for the first time today**: there was no saved copy. Its sections are in section 6.5 |
| [T-REG] | Registration form linked from the international track | `templates/team-information-form.xlsx` | 5,353 B, LM 08 Oct. Not downloaded (registration is outside this task). The older `international-registration-form-en.xlsx` (12,646 B) is still served but no longer linked |

**Is anything newer than 22 Sep 2026?** By date, yes: every file on the site, templates included, now shows Last-Modified **08 Oct 2026 12:56 GMT**. By content, no: every template's MD5 ETag matches the saved copy byte for byte, and the five re-fetched docx files have the same SHA-256. The bundles keep the same content-hashed names. The 8 Oct date is a redeploy of the whole site, not a new template. The only new reading is the README template, which was already linked on 1 Oct but had not been opened. Each template's footer still says "If a newer template is published, the newer version prevails", so re-run the check on 20 Oct (section 9).

## 2. Deadline

| Item | Value | Source | Status |
| --- | --- | --- | --- |
| Registration **and** submission deadline (one deadline) | **20 October 2026, 23:59 Beijing Time (UTC+8)** | [RULES-DOCX] §5 | VERIFIED (saved) |
| The same, on the site | "by 24:00 on 20 October (UTC+8)"; ZH "截止时间为 10 月 20 日 24:00（UTC+8）" | [SITE-RULES] | VERIFIED |
| Other time zones, as the docx gives them | 16:00 UTC; 17:00 London (BST); 09:00 US Pacific (PDT); 01:00 Tokyo and 03:00 Sydney on 21 Oct | [RULES-DOCX] §5 | VERIFIED (saved) |
| Clock for every date | "All dates use China Standard Time (UTC+8)" | [SITE-RULES], [SITE-HOME] | VERIFIED |
| Updates | "Submissions may be updated any time before the deadline; the latest version received prevails. No changes are accepted after the deadline." | [RULES-DOCX] §5 | VERIFIED (saved) |
| Reminder | A bilingual email reminder 24 hours before the deadline | [RULES-DOCX] §5 | VERIFIED (saved) |

**Cutoff to work to: 20 Oct 2026, 23:59 UTC+8 (15:59 UTC).** That is the earlier of the two official wordings (the site's 24:00 is one minute later). It is the same clock as Singapore time (SGT, UTC+8). ASSUMED: whether "received" means the time the email is sent or the time it arrives is not stated, so plan to send the final package by **20 Oct, 21:00 UTC+8** and leave room for large attachments or links.

Later dates (VERIFIED, [SITE-RULES] and [SITE-HOME]): compliance screening 21 Oct; online review 22–23 Oct (the home widget shows 23 Oct); finalists and invitations 31 Oct; check-in and WeBank visit 20 Nov; international defence 22 Nov in English at WeBank, Shenzhen; awards 23 Nov. At least one member of each finalist team must attend in person [RULES-DOCX] §6.

## 3. Deliverables: required or optional, and format

The two official sources disagree, so both are shown. The Chinese site prevails.

| # | Deliverable | [RULES-DOCX] §5 checklist | [SITE-RULES] EN / ZH label | Template and format the site links | Decision |
| --- | --- | --- | --- | --- | --- |
| 1 | Technical documentation | Listed: "system architecture, core algorithm description, security design" | Required / 必交 | DOCX · Required [T-TECH] | **Required.** Submit as DOCX, with a PDF copy (ASSUMED: no format is mandated; DOCX follows the template) |
| 2 | Presentation deck | Listed: "final presentation no longer than 10 minutes" | Required, up to 10 minutes / 必交, 不超过 10 分钟 | PPTX · Required [T-DECK] | **Required.** PPTX on the official template, with a PDF copy (ASSUMED as above) |
| 3 | Demo video | "(optional, no longer than 5 minutes)" | Required, up to 5 minutes / 必交, 不超过 5 分钟 | Guide: DOCX · Required [T-VIDEO]; the guide says "Required for the International AI Track" | **Required**, at most 5:00. No container or codec is specified (ABSENT) |
| 4 | Source code | Listed: "with README, GitHub repository link, deployment instructions, and test cases" | Optional / 可选 (grouped with 5 and 6) | README template: MD · Optional [T-README] | **Submit it.** It is optional on the site but listed without qualification in the docx |
| 5 | Security self-assessment report | Listed: "permission-tier implementation and known-risk list" | Optional / 可选 | DOCX · Optional [T-SEC] | **Submit it.** Same reasoning |
| 6 | Execution evidence | Listed: "for non-on-chain topics: simulated-account/sandbox operation logs and demo video" | Optional / 可选 | DOCX · Optional [T-EVID] | **Submit it.** It is the only evidence route the rules name for the 40% task-completion score |
| — | Registration form | Attachment 3, emailed back (notice) | "XLSX · Required" / 必交 | `team-information-form.xlsx` | Required, same deadline. Outside this document's scope (issue #10) |

**Formats and size limits.** There are no page, word, slide, font or file-size limits in any official source (ABSENT). The only numeric limits are the deck's 10 minutes and the video's 5 minutes. Video quality guidance [T-VIDEO]: "Use 16:9 landscape and preferably 1080p"; "Make interface text, narration and English subtitles clearly legible"; "No copyrighted or sensitive material"; "Suggested filename: Track-TeamName-DemoVideo".

**How to submit.** ABSENT for the materials. The site says only "Register by official email … and submit the required English materials" [SITE-RULES], and the notice says to return the registration form "to this mailbox", signed fintechathon@ican-x.com [SITE-NOTICE]. There is no upload portal. ASSUMED: one email to **fintechathon@ican-x.com**, the address the 2026 rules page lists as the International Track contact, with the documents attached and the video and any large files as a download link. Confirm through issue #9; section 8 explains the conflict between addresses.

## 4. Requirements checklist

"Package state" describes the branch `docs/techdoc-chat-fixes` at `571ea64f` on 18 Oct 2026.

| # | Requirement | Source and date | Status | How FLOW's package meets it, or what is missing |
| --- | --- | --- | --- | --- |
| R1 | Final package received by 20 Oct 2026 23:59 UTC+8; updates allowed until then, latest version prevails | [RULES-DOCX] §5 (file unchanged since 22 Sep; checked 18 Oct); [SITE-RULES] "24:00 (UTC+8)" (checked 18 Oct) | VERIFIED | Not yet sent. Plan the final send for 20 Oct 21:00 UTC+8 (section 2) |
| R2 | Technical documentation, required, covering system architecture, core algorithm description and security design | [RULES-DOCX] §5; [SITE-RULES] Required; [T-TECH] "Required material…" | VERIFIED | `docs/deliverables/technical_document.md`, built to `docs/deliverables/out/Technical_Document.docx` and `.pdf`. It uses the five template headings and all nine prompts verbatim (section 5) |
| R3 | The technical document follows the template: header table (Team name, Competition track, Submission date) and sections 01–05 | [T-TECH], unchanged, checked 18 Oct | VERIFIED | Done: the header reads ISMOGGER, "International AI Track, Topic E: SME Finance Copilot", 20 October 2026. Gap: the 30% security wording "induced transfers" and "data extraction" never appears in section 04 (0 and 1 hits). Add both names to 04 (section 7) |
| R4 | Presentation deck, required, at most 10 minutes of presenting | [RULES-DOCX] §5; [SITE-RULES] | VERIFIED | **Missing.** Only `docs/deliverables/deck_outline.md` exists (18 slides, 9:40 planned). No PPTX is built. The template's 2025 branding question is still open in the outline |
| R5 | The deck uses the official template | [SITE-RULES] links `presentation-template.pptx` as "PPTX · Required" | VERIFIED that the template is linked. ASSUMED that using it is mandatory | Build the deck on `docs/research/templates/presentation-template.pptx` (byte-identical to the live file). Replace the Chinese placeholders with English |
| R6 | Demo video, required, at most 5 minutes | [SITE-RULES] Required / 必交 (prevails over the docx "optional"); [T-VIDEO] | VERIFIED | `flow-demo-5min.webm`, 4:22, 31.7 MB, recorded 18 Oct, 1920×1080 (`docs/deliverables/video/README.md`). It is gitignored and stays on the recording machine. It is not yet linked from `execution_evidence.md` (still "[TEAM: link or file name of the demo video]") |
| R7 | Video: 16:9, 1080p preferred, legible interface text, narration and English subtitles, no copyrighted or sensitive material, filename "Track-TeamName-DemoVideo" | [T-VIDEO] | VERIFIED | 16:9 at 1080p: met. Subtitles: the recording has an English caption bar. Narration: the README does not mention any. ASSUMED: the caption bar can stand in for subtitles if there is no voice-over. Check this before sending. The filename needs renaming, for example `International-AI-Track-ISMOGGER-DemoVideo.mp4`. ASSUMED: also export an MP4 copy, since WebM does not play everywhere |
| R8 | Source code with README, GitHub repository link, deployment instructions and test cases | [RULES-DOCX] §5; [SITE-RULES] Optional | VERIFIED | README has Quickstart, Architecture, Testing, Security and Known limitations, and links the repository. `docs/deliverables/TEST_CASES.md` exists. **Gap: the repository is private** (`gh repo view`: PRIVATE). Judges cannot open the link unless it is made public or they are given access (issue #9 Q4) |
| R9 | The README follows the template's seven sections: Project Overview (Track, Team name, Project name, One-line summary), System Architecture with a diagram, Environment and Dependencies (operating system, runtime versions, main dependencies, environment variables), Installation and Execution, Testing, Repository and Deployment (repository, live demo if available, deployment instructions), Security Notes | [T-README], first read 18 Oct | VERIFIED | Partly met. The content exists, but the headings differ. No "Environment and Dependencies" or "Repository and Deployment" heading; no "Operating system" line; no "Live demo (if available)" line. The template says "Copy this file to the repository root and complete every relevant section in English". It is marked Optional |
| R10 | Security self-assessment covering permission-tier implementation and a known-risk list | [RULES-DOCX] §5; [T-SEC]; [SITE-RULES] Optional | VERIFIED | `docs/SECURITY_SELF_ASSESSMENT.md`, built to `out/Security_Self_Assessment.docx` and `.pdf`. Sections 01–04 match the template. Gap: the header table still holds "[TEAM: team name]" and "[TEAM: submission date]" |
| R11 | Execution evidence for a non-on-chain topic: simulated-account or sandbox logs **and** the demo video; per entry "Timestamp, action, result and relevant screenshot/link"; a reproduction guide for judges | [RULES-DOCX] §5; [T-EVID] | VERIFIED | `docs/deliverables/execution_evidence.md`, built to `out/Execution_Evidence.docx` and `.pdf`. Sections 01–03 match the template. Gaps: the header has three [TEAM:] placeholders, and the demo-video link is missing |
| R12 | All materials in English ("submitted materials must include an English version"); review and defence in English | [SITE-RULES]; [RULES-DOCX] §4(3); [T-TECH] and [T-SEC] "Please complete this document in English" | VERIFIED | All deliverables are in English. The app's Chinese screens and replies are a feature, not a language problem. Check that no Chinese-only page or slide reaches the deck or the video without English beside it |
| R13 | Topic E scope: "financing-option matching, cash-flow management and alerts, and business financial analysis"; site wording "Cash flow, reconciliation and operational recommendations" (小微企业财务助手：现金流、对账与经营建议) | [RULES-DOCX] §2; [SITE-HOME] | VERIFIED | The technical document covers the funding router (financing options), the cash forecast and alerts, covenant analysis, and reconciliation (12 hits). Section 01 should name these five scope words in one place (section 7) |
| R14 | Challenge brief: "deliver a working financial Agent that demonstrates intent understanding, task planning, safe execution, user control and measurable value in a financial scenario" | [SITE-HOME] English challenge brief | VERIFIED | Covered across 03 and 04. Not a scored criterion, but it is the organisers' own summary of the theme |
| R15 | Independent work; third-party data, code, open-source components and APIs legally licensed and compliant with their licences and data-use terms | [SITE-RULES]; [RULES-DOCX] §8 | VERIFIED | Gap: the README says "There is no LICENSE file yet". Third-party licences are not listed in one place. ASSUMED: a dependency-licence statement in the README or technical document 02 is enough |
| R16 | Integrity: no plagiarism or IP infringement; the organiser may use entries for non-commercial publicity | [SITE-RULES]; [RULES-DOCX] §8 | VERIFIED | Noted. Nothing to submit |
| R17 | No copyrighted or sensitive material in the video | [T-VIDEO] | VERIFIED | All data is synthetic. Check the video for third-party logos before sending |
| R18 | Eligibility: full-time students at universities outside China (including Hong Kong, Macao and Taiwan); team of 2–5; at least 60% non-Chinese nationals, rounded up; one team per person | [SITE-RULES]; [RULES-DOCX] §4 | VERIFIED | Team matter, outside this document (issues #5, #10). Screening is on 21 Oct |
| R19 | Anonymity | — | ABSENT | No anonymity or blind-review rule exists in any official source. All four docx templates require "Team name" in the header. See section 6 |
| R20 | File formats and size limits | — | ABSENT | None published (section 3). ASSUMED: DOCX or PPTX as the templates give them, plus PDF copies; MP4 video; send large files as links |
| R21 | Submission channel and email subject | — | ABSENT | ASSUMED: email to fintechathon@ican-x.com (section 3) |

## 5. Technical Document: mandatory sections and exact template prompts

From [T-TECH] (unchanged since 22 Sep; checked 18 Oct). The template opens with "2026 FINTECHATHON · SUBMISSION TEMPLATE", then "International AI Track | Technical Document" and "Required material for the International AI Track. Please complete this document in English." Its header table has three rows to fill in: **Team name**, **Competition track** and **Submission date**. Each prompt below is followed by "Write here" in the template. The footer says "Complete this document according to the competition notice. If a newer template is published, the newer version prevails."

| Section | Exact prompt | FLOW heading (technical_document.md) |
| --- | --- | --- |
| **01 Project Overview** | Problem, target users and selected topic | Same, line 46 |
| | Core value and innovation | Same, line 74 |
| **02 System Architecture** | Architecture diagram and component responsibilities | Same, line 169 |
| | Models, tools, data sources and external services | Same, line 225 |
| **03 Agent Design** | Intent understanding, planning, tool use and state management | Same, line 332 |
| | Core algorithms and evaluation approach | Same, line 481 |
| **04 Security Design** | Tiered permissions and confirmation for sensitive actions | Same, line 730 |
| | Protection against prompt injection, privilege escalation and privacy leakage | Same, line 804 |
| **05 Deployment and Testing** | Environment, deployment instructions, test cases and known limitations | Same, line 930 |

No page or word limit is set (ABSENT). The [RULES-DOCX] summary of the same deliverable is "system architecture, core algorithm description, security design", and sections 02, 03 and 04 cover it.

## 6. Other templates, anonymity and language

### 6.1 Security self-assessment [T-SEC]
"Optional supporting material. Please complete this document in English." Header: Team name, Competition track, Submission date.
- **01 Permission Model:** "Roles, operations and permission boundaries"; "Confirmation, verification and rollback mechanisms"
- **02 Security Tests:** "Prompt injection, social engineering, privilege escalation and failure recovery tests"
- **03 Data and Privacy:** "Data provenance, consent, minimisation, storage and deletion"
- **04 Known Risks:** "Risk, impact, mitigation and planned improvement"

### 6.2 Execution evidence [T-EVID]
"Optional supporting material for operation logs or on-chain transaction evidence." Header: as above.
- **01 Evidence Summary:** "Selected topic and scenario"; "What the evidence demonstrates"
- **02 Logs or Transactions:** "Simulated account/sandbox logs, or transaction hashes for Topic F"; "Timestamp, action, result and relevant screenshot/link"
- **03 Reproduction Guide:** "Steps required for judges to reproduce or verify the evidence"

### 6.3 Demo video guide [T-VIDEO]
"Required for the International AI Track. The video must be no longer than five minutes." Header: 队伍名称 / Team, 参赛赛道 / Track, 提交日期 / Date.
- **01 Recommended Structure:** "Project and team introduction"; "End-to-end demonstration of the core scenario"; "Safety mechanisms, innovation and results"
- **02 Video Quality:** "Use 16:9 landscape and preferably 1080p"; "Make interface text, narration and English subtitles clearly legible"
- **03 Final Check:** "No copyrighted or sensitive material"; "Suggested filename: Track-TeamName-DemoVideo"

ASSUMED: the guide is a checklist for making the video, not a document to submit. Nothing says to return it filled in.

### 6.4 Deck [T-DECK]
16:9, four slide types: title (作品名, 团队名), a contents slide with six items, a content slide and a closing slide. The 2025 logo is baked into the images (`docs/research/submission-templates.md` §5). There is no slide limit. The 10-minute limit comes from the site.

### 6.5 Source code README [T-README] (read 18 Oct 2026)
Title "2026 FinTechathon | Source Code README Template", with the instruction "Copy this file to the repository root and complete every relevant section in English." Sections: 1 Project Overview (Track; Team name; Project name; One-line summary); 2 System Architecture (main components, models, tools, data sources and their relationships, "Include an architecture diagram"); 3 Environment and Dependencies (Operating system; Runtime versions; Main dependencies; Environment variables, "never commit real secrets or sensitive data"); 4 Installation and Execution ("complete setup, configuration, launch and access instructions for a clean environment"); 5 Testing ("test commands, test cases, expected results and known limitations"); 6 Repository and Deployment (GitHub / Git repository; Live demo (if available); Deployment instructions); 7 Security Notes ("permission tiers, confirmation for sensitive operations, data handling and known risks").

### 6.6 Anonymity
- **No anonymity rule.** No official source asks for anonymised materials, and none mentions blind review (ABSENT; "blind", 盲审 and 匿名 searched in every 2026 bundle and the docx).
- The templates **require** the team name in every header, and the video guide asks for a "Project and team introduction".
- The spec's "expert blind review" (`topic-e-rules.md` §b) has no official source.
- **Proposed rule:** name the team (ISMOGGER) and the product (FLOW) everywhere. Keep members' personal data (passport or ID numbers, proof of enrolment) out of every deliverable and the repository; it belongs only in the registration form.

### 6.7 Language
- English is the official language. "Entry submission, presentations and judging are conducted in English, and submitted materials must include an English version" [SITE-RULES]; ZH "提交材料应包含英文版本".
- [RULES-DOCX] §4(3) says the same. [T-TECH] and [T-SEC] each say "Please complete this document in English". [T-VIDEO] asks for English subtitles. VERIFIED.

## 7. Judging rubric for Topic E, as published

All six international topics share one rubric: "All six International Track topics use the same core judging dimensions" [SITE-RULES]; "choosing the on-chain topic does not affect scoring" [RULES-DOCX] §3. No Topic E-specific criteria or sub-weights are published (ABSENT).

| Criterion (EN / ZH title) | Weight | Published description, EN [SITE-RULES] | Published description, ZH (prevails) |
| --- | --- | --- | --- |
| Task Completion / 任务完成率 | **40%** | "Completion of scripted tasks in a simulated environment for non-on-chain topics; Topic F is evaluated using on-chain transaction hashes." | 非链上方向以模拟环境中的脚本化任务完成度为准；方向 F 以真实链上交易哈希为依据。 |
| Security & Compliance / 安全合规性 | **30%** | "Defence against induced transfers, data extraction, privilege escalation and prompt injection; serious security failures trigger substantial deductions." | 统一考察对诱导转账、信息套取、越权操作和 Prompt 注入的防御能力；严重安全问题将触发大幅扣分。 |
| Innovation & Interaction / 创新性及交互体验 | **30%** | "Scenario novelty, real-world value, dialogue efficiency, clarification, correction and fallback capability." | 考察场景新颖性、真实问题解决度、轮次效率、追问、纠错和兜底能力。 |
| Bonus | **0–5 points, capped** | "A capped 0–5 point challenge/implementation bonus rewards advanced topics or demonstrated real-world deployment. Topic choice itself does not affect the base score." | 设置 0—5 分"挑战/落地加分"（封顶），奖励主动挑战高阶方向或实现真实落地的团队；方向选择本身不影响基础评分。 |

- The weights are the same in [RULES-DOCX] §3: "Task completion: 40%", "Security & compliance: 30%", "Innovation & interaction: 30%". The docx names the bonus "Challenge bonus (on-chain exploration): 0–5 points", which conflicts with the site's wording (section 8).
- Appeals: "within three business days after results are announced" [SITE-RULES].
- No sub-weights inside a criterion, no numeric scale per criterion and no rule on how the bonus combines with the base score are published (ABSENT).

### Criterion → where the technical document should answer it

Headings are the template's (section 5). "Now" says whether the current text answers in the rubric's own words.

| Rubric element | Technical document section that should answer | Now | Supporting deliverable |
| --- | --- | --- | --- |
| 40% scripted tasks in a simulated environment | 03 "Core algorithms and evaluation approach" (the scripted-task results); 05 "…test cases…" (how to rerun them) | Answered (49/49 scripted conversations, Tables 14 and 15). Use the words "scripted tasks" and "simulated environment" in 03 | Execution evidence 02 and 03; demo video |
| 40% the work itself: planning and tool use (challenge brief "intent understanding, task planning") | 03 "Intent understanding, planning, tool use and state management"; 02 "Models, tools, data sources…" | Answered | Execution evidence 02 |
| 30% induced transfers | 04 "Tiered permissions and confirmation for sensitive actions" | **Not named.** The text covers fake approvals and "owner has approved" claims but never says "induced transfer" (0 hits). Add a labelled paragraph | Security self-assessment 02 ("social engineering") |
| 30% data extraction | 04 "Protection against … privacy leakage" | **Barely named** (1 hit). Label the outbound-redaction defence "data extraction" | Security self-assessment 02 and 03 |
| 30% privilege escalation | 04 "Protection against prompt injection, privilege escalation…" | Answered | Security self-assessment 01 and 02 |
| 30% prompt injection | 04, same prompt | Answered | Security self-assessment 02 |
| 30% "serious security failures trigger substantial deductions" | 04, plus 05 "known limitations" | Answered in part (0 violations of the defined harm oracles across 279 attack cases). Put the honest open risks beside it | Security self-assessment 04 "Known Risks" |
| 30% scenario novelty | 01 "Core value and innovation" | Answered | Deck; video |
| 30% real-world value | 01 "Problem, target users and selected topic" | Answered | Deck |
| 30% dialogue efficiency | 03 "Intent understanding … state management" | Partly: there are turn counts, but no sentence calls it "dialogue efficiency". Give the average turns per task | Video |
| 30% clarification | 03, same prompt | Answered ("Clarification", line 398) | JUDGING_QUESTIONS |
| 30% correction | 03, same prompt | Answered ("Correction", line 399) | Video |
| 30% fallback (兜底, out of scope) | 03, same prompt; 02 (the rules-grammar fallback when a model fails) | Answered (out of scope, line 337; model fallback, line 243). Name it "fallback" in 03 | JUDGING_QUESTIONS Q6 soft spots |
| Bonus: advanced topic or real-world deployment | 05 "Environment, deployment instructions…" (what is deployed and where); 01 | Not claimed. FLOW is a simulation. ASSUMED: do not claim the bonus unless a real deployment exists | — |
| Topic E scope: financing-option matching; cash-flow management and alerts; business financial analysis; reconciliation; operational recommendations | 01 "Problem, target users and selected topic" (name all five); 03 "Core algorithms…" (router, forecast, alerts, covenants, reconciliation) | Covered piecemeal. Add one sentence in 01 that maps FLOW to the topic's own words | Video chapters 3, 9 and 11 |
| Challenge brief: "safe execution, user control and measurable value" | 04 (safe execution, user control); 03 evaluation (measurable value) | Answered | — |

## 8. Conflicts between official sources

| Topic | Source A | Source B | Resolution |
| --- | --- | --- | --- |
| Demo video | [RULES-DOCX]: "optional" | [SITE-RULES] EN "Required", ZH 必交; [T-VIDEO] "Required" | **Required** (the Chinese version prevails, and the guide agrees) |
| Source code, security self-assessment, execution evidence | [RULES-DOCX]: listed with no "optional" | [SITE-RULES]: "Optional" / 可选 | Submit all three. It costs nothing and the 40% relies on the evidence |
| Bonus | [RULES-DOCX]: "(on-chain exploration)" | [SITE-RULES]: "advanced topics or demonstrated real-world deployment" | The site's Chinese text prevails (挑战/落地). Topic E could earn it only through real deployment. Not claimed |
| Cutoff | [RULES-DOCX]: 23:59 UTC+8 | [SITE-RULES]: 24:00 UTC+8 | Work to 23:59 |
| Team nationality quota | [RULES-DOCX]: "should be" at least 60% | [SITE-RULES]: "must" / 须 | "Must" (Chinese prevails) |
| Contact and submission address | [RULES-DOCX] §9: info@ican-x.com | [SITE-NOTICE] and the [SITE-RULES] international contact: **fintechathon@ican-x.com**. [SITE-HOME] and the domestic rules: fintechathon@g-ican.com | ASSUMED: **fintechathon@ican-x.com**, the only address the 2026 rules page gives for the International Track. Note: the draft organiser email in issue #9 is addressed to fintechathon@g-ican.com, the domestic AI address. Re-address it to fintechathon@ican-x.com and cc info@ican-x.com |

**Strings on the site that do not apply.** Do not cite these.
- `js/app.83e69cd7.js` holds a home-page "Judging Criteria" block for an "Artificial Intelligence Track": 40% "Completeness of Implementation", 30% "Innovation", 30% "Business Value".
- `js/lang-en-US-rule.5d04a38a.js` describes an email submission to fintechathon@g-ican.com with the subject "[Name of Team + Name of Works]", a "Caiwei platform" and FISCO BCOS. It is from an earlier edition.
- Neither is the 2026 International Track rules page, which [SITE-RULES] is. [SITE-RULES] agrees with [RULES-DOCX] on 40/30/30.

## 9. Unverified items and the proposed assumptions

| # | Item | Why it cannot be verified | Proposed assumption |
| --- | --- | --- | --- |
| U1 | How to submit the materials (email, portal, link) and the email subject | ABSENT: the site says only "Register by official email" | One email to fintechathon@ican-x.com, cc info@ican-x.com. Subject "FinTechathon 2026 International AI Track – Topic E – ISMOGGER – FLOW submission". Documents attached, video and large files linked |
| U2 | Whether "received" means sent or arrived | ABSENT | Send by 20 Oct, 21:00 UTC+8 |
| U3 | File formats and size limits | ABSENT | DOCX or PPTX as the templates give them, each with a PDF copy. The video as MP4 (H.264), 1080p, under 5:00, linked rather than attached if it is over about 20 MB |
| U4 | Whether the GitHub repository must be public | ABSENT (the docx asks for a "GitHub repository link"; issue #9 Q4 is unanswered) | Judges must be able to open the link without asking. Either make the repository public before sending, after a secrets check, or give reviewers read access and say so in the email. The team decides. The repository is PRIVATE today |
| U5 | Whether judges run their own scripted tasks against a live agent | ABSENT (issue #9 Q1) | No. Task completion is judged from the execution evidence, the video and the reproducible scripts (`scripts/judge_eval.py`, `scripts/verify_evidence.py`) |
| U6 | Whether the video needs a voice-over, or whether captions are enough | [T-VIDEO] names "narration and English subtitles" as things that must be legible; it does not say narration is mandatory | Captions are acceptable. If there is time, add English narration with matching subtitles |
| U7 | Whether the deck must use the official template, and whether the 2025 logo is acceptable | The site links it as "PPTX · Required"; that may mean the deck is required rather than the template | Use the official file, replacing only the placeholder text (deck_outline option A) |
| U8 | Whether the README must follow [T-README]'s headings | Marked "MD · Optional" | Add the two missing headings (Environment and Dependencies; Repository and Deployment) and an "Operating system" line, or a short template-shaped section that links to the existing ones |
| U9 | Anonymity | ABSENT | Not anonymous: name the team and the product (section 6.6) |
| U10 | Sub-weights inside each criterion; how the bonus is added | ABSENT | None. Address every phrase of each criterion (section 7 index) |
| U11 | Whether a newer template appears before the deadline | The footer says a newer version prevails | On 20 Oct, rerun `curl -sI` on the eight template URLs and compare each ETag with the MD5 values in section 1. Any change means re-reading that template |

## 10. To fix before sending (from the checklist)

1. Build the deck (R4, R5). It is the only required deliverable that does not exist yet.
2. Settle repository access (R8, U4).
3. Fill the [TEAM:] placeholders in `execution_evidence.md` and `SECURITY_SELF_ASSESSMENT.md`, link the video, and rebuild the docx files (R10, R11).
4. Rename the video, export an MP4 copy, and check captions and logos (R6, R7, R17).
5. Technical document 04: name "induced transfers" and "data extraction". Technical document 01: one sentence mapping FLOW to Topic E's words. Technical document 03: say "dialogue efficiency" and "fallback" (R3, R13; section 7 index).
6. README: add the template's missing headings, and a licence or dependency-licence statement (R9, R15).
7. Re-address the organiser email in issue #9 to fintechathon@ican-x.com (section 8).
8. On 20 Oct, recheck the templates (U11), then send by 21:00 UTC+8.
