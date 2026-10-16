# smu2sz

## Agent skills

### Issue tracker

Issues live in GitHub Issues for peachoolongtee/smu2sz (gh CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Branching and integration

Read `docs/agents/integration.md` before starting any branch: branch from the latest dev, bring dev in daily, run the
full mock browser suite before handing in, and leave merges into dev to the lead.

## Handover

Continuing this project in a new session or on another machine: read `docs/HANDOVER.md` first. It holds the
owner's standing instructions, the current state, and what to do next. The live tracker is `docs/NEXT_FIXES.md`.

The CAPEX buy-side work (branch `feat/capex-buy-side`, ADR-0013) has its own handover: `docs/capex_handover.md`. Read it
before touching `app/capex`, `app/health`, `app/lending` or the capex contract kind, and update it with every change.
