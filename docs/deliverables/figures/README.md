# Figures for the technical document

Seven PNG figures for FLOW's final technical document. Each one is 2400 px wide (8 in at 300 dpi) on white. Each has a
matplotlib source in `src/` that regenerates it. The style lives in `src/flowstyle.py`:

- **Palette:** the FLOW brand from `apps/web/app/globals.css`. Brand blue `#0368e9`, ink `#24324a`, purple `#9252dc`,
  amber `#b7791f` and grey `#768399`. There is no red-green pair.
- **Fonts:** Microsoft YaHei, so Chinese renders; Noto Sans SC is the fallback.
- **Size:** the smallest text is 13.5 pt at 8 in, which prints at 11 pt when the figure is 6.5 in wide.

`scripts/build_deliverables.py` embeds a figure at 6.4 in, so the smallest text prints at about 10.8 pt.

**Render** one figure from `src/`:

```bash
uv run --no-project --with matplotlib --with pillow python fig1_architecture.py
```

**Embed** a figure in `docs/deliverables/*.md`. The path is relative to that folder:

```markdown
<!-- figure: figures/fig1-architecture.png | Figure 1. ... -->
```

| Figure | Caption | Source | Data |
| --- | --- | --- | --- |
| `fig1-architecture.png` | FLOW in one picture: the compiler is the only model-backed step, the verifier decides on typed obligations, and only the executor writes. | `src/fig1_architecture.py` | Read from the code on dev `975e082f`: `app/compiler` (redaction, grounding, coverage), `app/verifier`, `app/financial`, `app/funding`, `app/operations/executor.py`, `app/mandate/tiers.py`, `app/api/auth.py` (bank feed) |
| `fig2-offer-lifecycle.png` | One buyer request from message to money, marking which steps run on their own, which wait for the owner and which are simulated. | `src/fig2_offer_lifecycle.py` | `app/api/offers.py`, `decide.py` (`/evaluate`, `/negotiate`), `accept.py`, `outbound.py` (`/offered`, `/buyer-accepted`), the executor's `AcceptOffer`, `app/commitments`, `app/alerts/reconcile.py`; outcomes from `app/domain/models.py` `Outcome` |
| `fig3-permission-tiers.png` | Who may do what: the three permission tiers with examples, and the executor's gates in the order the code runs them. | `src/fig3_permission_tiers.py` | `app/mandate/tiers.py` (`tier_for`), `app/operations/executor.py` (`_run`, `_screen_commitment`, `_handle`) |
| `fig4-golden-cash.png` | The golden books' cash over 60 days: without new funding, cash falls below the ¥300k minimum on day 12; FLOW's plan keeps it at or above the minimum. | `src/fig4_golden_cash.py` | `GET /home` on the golden books, in-process (TestClient, `LLM_MODE=cache`, `DATABASE_URL=memory`, `DEMO_MODE=1`), `cash.series` and `cash.plan_series`. The values are printed in the script, and `--fetch` refreshes them. |
| `fig5-heldout-results.png` | The compiler's held-out results, each labelled as unseen or tuned on: no misread message was accepted without the owner after ADR-0005. | `src/fig5_heldout_results.py` | First run and live DeepSeek rows: `services/api/evals/accuracy_summary.md` (1 Oct 2026, 389cfd9). Today rows and form baseline: `../evidence/EVIDENCE_PACK.md` section 1 (dev 975e082f, 17 Oct 2026) |
| `fig6-contract-reading.png` | Reading Chinese contracts, by format: 98% on the tuned batch, 75% on the held-out batch, 86% after the fixes, and nothing from scans or photos, which have no OCR. | `src/fig6_contract_reading.py` | Scoring logs of 16–17 Oct 2026 (`b2fix/b1-redact.log`, `b2fix/b2-redact.log`, `contract-cn2/mismatches.csv` = `b2fix/b2-base.log`). These are not in the repo, so the script quotes the per-format rows. |
| `fig7-security-results.png` | The attack catalogue: 260 stored cases by class, none violating the defined harm oracles; all reached their path, 119 of 127 API cases stopped by the named control. | `src/fig7_security_results.py` | `services/api/evals/security/latest_report.json` (regenerated in round four, 17 Oct 2026) |
