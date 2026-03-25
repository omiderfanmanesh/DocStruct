"""Unit tests for configuration classes."""

import os
from unittest.mock import patch

import pytest

from docstruct.config import (
    AgentConfig,
    ContextConfig,
    RetrievalConfig,
    ScoringConfig,
)


class TestScoringConfig:
    def test_defaults(self):
        config = ScoringConfig()
        assert config.scope_mention_bonus == 8
        assert config.node_title_weight == 4
        assert config.doc_submission_bonus == 26
        assert config.ranking_penalty == -8

    def test_from_env(self):
        with patch.dict(os.environ, {"SCORING_SCOPE_MENTION_BONUS": "12"}):
            config = ScoringConfig.from_env()
            assert config.scope_mention_bonus == 12


class TestContextConfig:
    def test_defaults(self):
        config = ContextConfig()
        assert config.max_chars_per_block == 1600
        assert config.total_context_budget == 12000
        assert config.max_context_blocks == 8
        assert config.dynamic_sizing is True

    def test_effective_max_chars_static(self):
        config = ContextConfig(dynamic_sizing=False)
        assert config.effective_max_chars(10) == 1600

    def test_effective_max_chars_dynamic(self):
        config = ContextConfig(
            dynamic_sizing=True,
            total_context_budget=12000,
            max_chars_per_block=2000,
            max_context_blocks=8,
        )
        # With 3 nodes, estimated blocks = min(6, 8) = 6
        # dynamic = 12000 // 6 = 2000, but capped at max_chars_per_block=2000
        result = config.effective_max_chars(3)
        assert result <= 2000

    def test_effective_max_chars_many_nodes(self):
        config = ContextConfig(
            dynamic_sizing=True,
            total_context_budget=12000,
            max_chars_per_block=2000,
            max_context_blocks=8,
        )
        # With 6 nodes, estimated blocks = min(12, 8) = 8
        # dynamic = 12000 // 8 = 1500
        result = config.effective_max_chars(6)
        assert result == 1500

    def test_effective_max_chars_zero_nodes(self):
        config = ContextConfig(dynamic_sizing=True)
        assert config.effective_max_chars(0) == config.max_chars_per_block

    def test_from_env(self):
        with patch.dict(os.environ, {"CONTEXT_MAX_BLOCKS": "12"}):
            config = ContextConfig.from_env()
            assert config.max_context_blocks == 12


class TestRetrievalConfig:
    def test_at_least_one_mode_required(self):
        with patch.dict(os.environ, {
            "RETRIEVAL_ENABLE_GRAPH": "false",
            "RETRIEVAL_ENABLE_FULLTEXT": "false",
            "RETRIEVAL_ENABLE_VECTOR": "false",
        }):
            with pytest.raises(ValueError, match="At least one"):
                RetrievalConfig.from_env()


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig()
        assert config.temperature == 0.0
        assert config.retry_count == 3
