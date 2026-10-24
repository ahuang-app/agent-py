"""Unit tests for the LLM usage budget service and configuration validation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from super_ai.llm.budget import (
    LlmBudgetExceededError,
    LlmBudgetService,
    capture_usage_metadata,
    estimate_text_tokens,
)
from super_ai.llm.config import LlmBudgetConfig, load_llm_budget_config
from super_ai.project_config import ProjectConfigurationError

NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class _UsageEvent:
    owner_user_id: str
    kind: str
    total_tokens: int
    estimated: bool
    created_at: datetime


class FakeUsageRepository:
    """In-memory LlmUsageRepository double for budget tests."""

    def __init__(self) -> None:
        self.events: list[_UsageEvent] = []

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
    ) -> None:
        self.events.append(
            _UsageEvent(
                owner_user_id=owner_user_id,
                kind=kind,
                total_tokens=total_tokens,
                estimated=estimated,
                created_at=created_at,
            )
        )

    async def sum_tokens_for_owner_between(
        self, *, owner_user_id: str, start_at: datetime, end_at: datetime
    ) -> int:
        return sum(
            event.total_tokens
            for event in self.events
            if event.owner_user_id == owner_user_id
            and start_at <= event.created_at < end_at
        )

    async def sum_tokens_between(self, *, start_at: datetime, end_at: datetime) -> int:
        return sum(
            event.total_tokens for event in self.events if start_at <= event.created_at < end_at
        )


def _service(**budget_values: int) -> LlmBudgetService:
    return LlmBudgetService(
        repository=FakeUsageRepository(),
        budget=LlmBudgetConfig(**budget_values),
    )


async def test_record_usage_persists_total_and_estimated_flag() -> None:
    repository = FakeUsageRepository()
    service = LlmBudgetService(
        repository=repository,
        budget=LlmBudgetConfig(per_user_daily_tokens=1_000),
    )
    await service.record_usage(
        owner_user_id="user_1",
        kind="chat",
        input_tokens=120,
        output_tokens=80,
        now=NOW,
    )
    await service.record_usage(
        owner_user_id="user_1",
        kind="embedding",
        input_tokens=500,
        output_tokens=0,
        estimated=True,
        now=NOW,
    )

    assert len(repository.events) == 2
    assert repository.events[0].total_tokens == 200
    assert repository.events[0].estimated is False
    assert repository.events[1].estimated is True
    used = await repository.sum_tokens_for_owner_between(
        owner_user_id="user_1",
        start_at=NOW.replace(hour=0, minute=0, second=0, microsecond=0),
        end_at=NOW.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
    )
    assert used == 700


async def test_daily_budget_blocks_within_day_and_resets_next_day() -> None:
    service = _service(per_user_daily_tokens=1_000)
    await service.record_usage(
        owner_user_id="user_1", kind="chat", input_tokens=700, output_tokens=200, now=NOW
    )
    with pytest.raises(LlmBudgetExceededError) as exc_info:
        await service.ensure_within_budget(
            owner_user_id="user_1", kind="chat", estimated_cost_tokens=200, now=NOW
        )
    assert exc_info.value.scope == "daily"

    await service.ensure_within_budget(
        owner_user_id="user_1",
        kind="chat",
        estimated_cost_tokens=200,
        now=NOW + timedelta(days=1),
    )


async def test_global_monthly_budget_is_cross_owner_and_resets_next_month() -> None:
    service = _service(global_monthly_tokens=1_000)
    await service.record_usage(
        owner_user_id="user_1", kind="chat", input_tokens=600, output_tokens=300, now=NOW
    )
    with pytest.raises(LlmBudgetExceededError) as exc_info:
        await service.ensure_within_budget(
            owner_user_id="user_2", kind="chat", estimated_cost_tokens=200, now=NOW
        )
    assert exc_info.value.scope == "monthly"
    assert "平台本月" in exc_info.value.message

    await service.ensure_within_budget(
        owner_user_id="user_2",
        kind="chat",
        estimated_cost_tokens=200,
        now=NOW + timedelta(days=20),
    )


async def test_owner_scope_excludes_other_users_from_daily_budget() -> None:
    service = _service(per_user_daily_tokens=500)
    await service.record_usage(
        owner_user_id="user_1", kind="chat", input_tokens=400, output_tokens=100, now=NOW
    )
    await service.ensure_within_budget(
        owner_user_id="user_2", kind="chat", estimated_cost_tokens=400, now=NOW
    )


async def test_unset_budgets_allow_any_usage() -> None:
    service = _service()
    await service.record_usage(
        owner_user_id="user_1", kind="chat", input_tokens=1_000_000, output_tokens=0, now=NOW
    )
    await service.ensure_within_budget(
        owner_user_id="user_1", kind="chat", estimated_cost_tokens=1_000_000, now=NOW
    )


def test_estimate_text_tokens_is_deterministic() -> None:
    texts = ["重启 API 服务", "Restart the api service"]
    assert estimate_text_tokens(texts) == estimate_text_tokens(texts)
    assert estimate_text_tokens([]) == 0


def test_capture_usage_metadata_reads_langchain_shape() -> None:
    usage = capture_usage_metadata({"input_tokens": 12, "output_tokens": 34})
    assert usage is not None
    assert usage.input_tokens == 12
    assert usage.output_tokens == 34
    assert capture_usage_metadata({"input_tokens": "12"}) is None
    assert capture_usage_metadata(None) is None


def test_budget_config_rejects_non_positive_values() -> None:
    with pytest.raises(ProjectConfigurationError):
        load_llm_budget_config({"budget": {"perUserDailyTokens": 0}})
    with pytest.raises(ProjectConfigurationError):
        load_llm_budget_config({"budget": {"globalMonthlyTokens": -5}})
    with pytest.raises(ProjectConfigurationError):
        load_llm_budget_config({"budget": {"perCallMaxOutputTokens": "many"}})
    with pytest.raises(ProjectConfigurationError):
        load_llm_budget_config({"budget": []})


def test_budget_config_defaults_and_valid_values() -> None:
    assert load_llm_budget_config({}) == LlmBudgetConfig()
    parsed = load_llm_budget_config(
        {
            "budget": {
                "perCallMaxOutputTokens": 2048,
                "perUserDailyTokens": 100_000,
                "globalMonthlyTokens": 1_000_000,
            }
        }
    )
    assert parsed == LlmBudgetConfig(
        per_call_max_output_tokens=2048,
        per_user_daily_tokens=100_000,
        global_monthly_tokens=1_000_000,
    )
