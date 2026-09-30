"""Canary values: synthetic secrets planted where only a leak could surface them.

`fixtures/security/canaries.yaml` lists each canary and where it is planted. A canary is never
entitled to any recipient (not even the owner) and can never be allowed, so any appearance of one in
LLM output or outbound text is a leak by definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.fixtures import FIXTURES
from app.egress.values import Category, PrivateValue

CANARIES_YAML: Path = FIXTURES / "security" / "canaries.yaml"


@dataclass(frozen=True, slots=True)
class Canary:
    id: str
    planted_in: str  # system_prompt | hidden_field | private_note
    where: str
    token: str | None = field(default=None, repr=False)
    amount_fen: int | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (self.token is None) == (self.amount_fen is None):
            raise ValueError(f"canary {self.id}: exactly one of token / amount_fen")
        if self.token is not None and len(self.token) < 8:
            raise ValueError(f"canary {self.id}: token too short to be distinctive")

    @property
    def label(self) -> str:
        return f"canary.{self.id}"

    def private_value(self) -> PrivateValue:
        """This canary as a protected value (owner: nobody, not even the SME owner)."""
        if self.token is not None:
            return PrivateValue.text(self.label, self.token, category=Category.CANARY, owner_visible=False)
        return PrivateValue.money(self.label, int(self.amount_fen or 0), category=Category.CANARY,
                                  owner_visible=False)


def _parse(raw: dict) -> tuple[Canary, ...]:
    out = []
    for c in raw["canaries"]:
        out.append(Canary(id=c["id"], planted_in=c["planted_in"], where=c.get("where", ""),
                          token=c.get("token"), amount_fen=c.get("amount_fen")))
    ids = [c.id for c in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate canary id")
    return tuple(out)


@lru_cache
def _load_default() -> tuple[Canary, ...]:
    return _parse(yaml.safe_load(CANARIES_YAML.read_text(encoding="utf-8")))


def load_canaries(path: Path | None = None) -> tuple[Canary, ...]:
    """The canaries in `fixtures/security/canaries.yaml` (or another file with the same shape)."""
    if path is None:
        return _load_default()
    return _parse(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def canary(canary_id: str) -> Canary:
    for c in load_canaries():
        if c.id == canary_id:
            return c
    raise KeyError(canary_id)
