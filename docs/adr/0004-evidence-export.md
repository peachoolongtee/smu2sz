# ADR-0004: What the execution evidence contains, and what the hash covers

The official template asks for a "timestamp, action, result and relevant screenshot/link" per entry, with steps judges can follow to reproduce. It defines no schema.

- Each operation line carries:
  - the simulated **day** as its timestamp;
  - the action (`kind`, `requested_by`, the full `payload_json`);
  - the result (`status`, `tier`, violation codes, `message`, the full `result_json`);
  - the hash links;
  - an optional `screenshot` path added by the scenario runner.
- The hash chain covers only `prev_hash + payload_json + result_json`. Wall-clock time goes into the `run` header alone, **outside every hash**, so replaying a scenario in cache mode reproduces the same head hash. That's what makes the evidence reproducible.
- Security events are exported as their own records. Refusals that never reached the executor, such as a FastCapital message stopped at the verifier, still appear in the evidence.
- `scripts/verify_evidence.py` uses the standard library only. Judges can recompute every hash without installing our code.
