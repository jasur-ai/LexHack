"""Tests for 7-Category Adversarial Trap Engine."""

import pytest

from evaluator_agent.config import AuditorSettings
from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import AdversarialCategory
from evaluator_agent.trap_engine import AdversarialTrapEngine


@pytest.mark.asyncio
async def test_all_seven_categories_present_in_trap_bank() -> None:
    llm = AuditorLLMClient(AuditorSettings(auditor_llm_provider="mock"))
    engine = AdversarialTrapEngine(llm)
    traps = engine.list_curated_traps()
    present = {t.category for t in traps}
    assert present == set(AdversarialCategory)

    suite = await engine.build_batch_suite(count=7, use_llm_generation=False)
    assert len(suite) == 7
