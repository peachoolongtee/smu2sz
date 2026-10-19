# Security policy

## Reporting a vulnerability

Please report a vulnerability privately:

- open a private security advisory on this repository (the **Security** tab, then **Report a vulnerability**), or
- contact the owner through the GitHub profile of the repository's owner.

Please do not open a public issue for a vulnerability. Say what you found, how to reproduce it and the commit you tested.

## Scope

FLOW (code name TermsLedger) is a hackathon simulation built for the 2026 FinTechathon. No production deployment exists:
the books, the buyers, the bank feed, the lenders and the clock are simulated, and every figure in the repository is
synthetic.

- In scope: the code in this repository, run as documented in `README.md` (the API in `services/api`, the web app in
  `apps/web`).
- Not a vulnerability: the demo credentials and tokens (for example `demo-owner-token`). They are published on purpose so
  that anyone can run the demo, and they only work when `DEMO_MODE=1`.
- Out of scope: third-party services and dependencies themselves (report those to their maintainers).

## What we have already assessed

- `docs/SECURITY_SELF_ASSESSMENT.md`: the security self-assessment, its scope, controls and known limits.
- `docs/security/`: the findings register, certifications, release gate and attack-surface plan.
