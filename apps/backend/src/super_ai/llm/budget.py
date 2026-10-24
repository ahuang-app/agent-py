"""LLM usage budget accounting and enforcement."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol, cast

from langchain_core.messages.utils import count_tokens_approximately

from super_ai.llm.config import LlmBudgetConfig


class LlmBudgetExceededError(RuntimeError):
    """Raised when an LLM call would exceed a configured usage budget."""

    def __init__(self, *, scope: str, message: str) -> None:
        super().__init__(message)
        self.scope = scope
        self.message = message


class LlmUsageRepository(Protocol):
    """Owner-scoped persistence for LLM usage events."""

    async def append(
        self,
        *,
        owner_user_id: str,
        kind: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        estimated: bool,
        created_at: datetime,
    ) -> None: ...

    async def sum_tokens_for_owner_between(
        self, *, owner_user_id: str, start_at: datetime, end_at: datetime
    ) -> int: ...

    async def sum_tokens_between(self, *, start_at: datetime, end_at: datetime) -> int: ...


def estimate_text_tokens(texts: Sequence[str]) -> int:
    """Deterministically estimate the token count of raw prompt texts."""
    total = 0
    for text in texts:
        if not text:
            continue
        total += count_tokens_approximately([{"role": "user", "content": text}])
    return total


def _start_of_utc_day(value: datetime) -> datetime:
    normalized = value.astimezone(timezone.utc)
    return normalized.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_utc_month(value: datetime) -> datetime:
    day_start = _start_of_utc_day(value)
    return day_start.replace(day=1)


def _next_month(value: datetime) -> datetime:
    month_start = _start_of_utc_month(value)
    if month_start.month == 12:
        return month_start.replace(year=month_start.year + 1, month=1)
    return month_start.replace(month=month_start.month + 1)


class LlmBudgetService:
    """Check configured budgets before LLM calls and record usage afterwards."""

    def __init__(
        self,
        *,
        repository: LlmUsageRepository,
        budget: LlmBudgetConfig,
    ) -> None:
        self._repository = repository
        self._budget = budget

    async def ensure_within_budget(
        self,
        *,
        owner_user_id: str,
        kind: str,
        estimated_cost_tokens: int = 0,
        now: datetime | None = None,
    ) -> None:
        """Raise LlmBudgetExceededError when the call would exceed a budget."""
        current = now if now is not None else datetime.now(tz=timezone.utc)
        per_user_daily = self._budget.per_user_daily_tokens
        if per_user_daily is not None:
            day_start = _start_of_utc_day(current)
            used = await self._repository.sum_tokens_for_owner_between(
                owner_user_id=owner_user_id,
                start_at=day_start,
                end_at=day_start + timedelta(days=1),
            )
            if used + max(estimated_cost_tokens, 0) > per_user_daily:
                raise LlmBudgetExceededError(
                    scope="daily",
                    message="你今天的模型用量已达到个人限额，请明天再试或联系管理员调整预算。",
                )
        global_monthly = self._budget.global_monthly_tokens
        if global_monthly is not None:
            month_start = _start_of_utc_month(current)
            month_end = _next_month(current)
            used = await self._repository.sum_tokens_between(
                start_at=month_start, end_at=month_end
            )
            if used + max(estimated_cost_tokens, 0) > global_monthly:
                raise LlmBudgetExceededError(
                    scope="monthly",
                    message="平台本月模型用量总额度已用尽，请联系管理员调整预算后重试。",
                )

    async def record_usage(
        self,
        *,
        owner_user_id: str,
        kind: str,
        input_tokens: int,
        output_tokens: int,
        estimated: bool = False,
        now: datetime | None = None,
    ) -> None:
        current = now if now is not None else datetime.now(tz=timezone.utc)
        input_value = max(input_tokens, 0)
        output_value = max(output_tokens, 0)
        await self._repository.append(
            owner_user_id=owner_user_id,
            kind=kind,
            input_tokens=input_value,
            output_tokens=output_value,
            total_tokens=input_value + output_value,
            estimated=estimated,
            created_at=current,
        )


@dataclass(frozen=True, slots=True)
class CapturedModelUsage:
    """Token usage reported by a completed chat model response."""

    input_tokens: int
    output_tokens: int


def capture_usage_metadata(usage: object) -> CapturedModelUsage | None:
    """Extract token counts from a LangChain usage_metadata mapping if present."""
    if not isinstance(usage, Mapping):
        return None
    usage_mapping = cast(Mapping[object, object], usage)
    input_tokens = usage_mapping.get("input_tokens")
    output_tokens = usage_mapping.get("output_tokens")
    if not isinstance(input_tokens, int) or isinstance(input_tokens, bool):
        return None
    if not isinstance(output_tokens, int) or isinstance(output_tokens, bool):
        return None
    return CapturedModelUsage(input_tokens=input_tokens, output_tokens=output_tokens)
