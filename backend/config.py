from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file() -> None:
    """Load local development variables without overwriting the real environment."""
    root = Path(__file__).resolve().parent.parent
    for filename in (".env.local", ".env"):
        path = root / filename
        if not path.exists():
            continue

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file()


@dataclass(frozen=True)
class AgentBudget:
    max_candidates: int = 5
    max_web_fetches: int = 10
    max_searches: int = 5
    snippets_per_search: int = 10
    fetches_per_search: int = 3
    target_average_usd: float = 0.30
    hard_ceiling_usd: float = 1.00


BUDGET = AgentBudget()
TRIAGE_MODEL = os.getenv("OPENAI_TRIAGE_MODEL", "gpt-4.1-nano")
GUARDRAIL_MODEL = os.getenv("OPENAI_GUARDRAIL_MODEL", "gpt-4.1-mini")
ANSWER_MODEL = os.getenv("OPENAI_ANSWER_MODEL", "gpt-4.1-mini")
FINAL_ANSWER_COST_RESERVE_USD = 0.05
