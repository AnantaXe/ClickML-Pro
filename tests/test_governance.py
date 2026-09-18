"""Tests for governance module."""

import pytest
from clickml_pro.governance.cost import CostEstimator, CostEstimate
from clickml_pro.governance.budget import BudgetManager
from clickml_pro.governance.quotas import QuotaManager
from clickml_pro.governance.policies import PolicyEngine, Policy, PolicyStatement, Action, Effect


class TestCostEstimator:
    def test_training_estimate(self):
        estimator = CostEstimator(budget_limit=10000, spent=0)
        est = estimator.estimate({
            "type": "training",
            "base_model": "llama-7b",
            "mode": "finetune",
            "training": {"epochs": 3, "batch_size": 4},
        })
        assert isinstance(est, CostEstimate)
        assert est.cost_usd > 0
        assert est.gpu_hours > 0
        assert est.within_budget is True

    def test_lora_cheaper_than_finetune(self):
        estimator = CostEstimator(budget_limit=10000, spent=0)
        ft = estimator.estimate({
            "type": "training", "base_model": "llama-7b",
            "mode": "finetune", "training": {"epochs": 3, "batch_size": 4},
        })
        lora = estimator.estimate({
            "type": "training", "base_model": "llama-7b",
            "mode": "lora", "training": {"epochs": 3, "batch_size": 4},
        })
        assert lora.cost_usd < ft.cost_usd

    def test_over_budget_warning(self):
        estimator = CostEstimator(budget_limit=1.0, spent=0.5)
        est = estimator.estimate({
            "type": "training", "base_model": "llama-70b",
            "mode": "finetune", "training": {"epochs": 10, "batch_size": 1},
        })
        assert est.within_budget is False
        assert len(est.warnings) > 0


class TestBudgetManager:
    def test_set_and_check_budget(self, tmp_path):
        mgr = BudgetManager(storage_dir=tmp_path)
        mgr.set_budget("org-1", limit_usd=100.0)

        result = mgr.check_budget("org-1", estimated_cost=50.0)
        assert result["allowed"] is True

    def test_exceed_budget(self, tmp_path):
        mgr = BudgetManager(storage_dir=tmp_path)
        mgr.set_budget("org-1", limit_usd=10.0)
        mgr.record_charge("org-1", 8.0, "job-1")

        result = mgr.check_budget("org-1", estimated_cost=5.0)
        assert result["allowed"] is False

    def test_no_budget_allows(self, tmp_path):
        mgr = BudgetManager(storage_dir=tmp_path)
        result = mgr.check_budget("unknown-org", estimated_cost=1000.0)
        assert result["allowed"] is True


class TestQuotaManager:
    def test_set_and_check_quota(self, tmp_path):
        mgr = QuotaManager(storage_dir=tmp_path)
        mgr.set_quota("team-a", gpu_hours_limit=50.0, max_concurrent_jobs=2)

        result = mgr.check_quota("team-a", requested_hours=10.0)
        assert result["allowed"] is True

    def test_exceed_hours(self, tmp_path):
        mgr = QuotaManager(storage_dir=tmp_path)
        mgr.set_quota("team-a", gpu_hours_limit=10.0)
        mgr.record_usage("team-a", 9.0)

        result = mgr.check_quota("team-a", requested_hours=5.0)
        assert result["allowed"] is False

    def test_concurrent_limit(self, tmp_path):
        mgr = QuotaManager(storage_dir=tmp_path)
        mgr.set_quota("team-a", gpu_hours_limit=100.0, max_concurrent_jobs=1)
        mgr.job_started("team-a")

        result = mgr.check_quota("team-a", requested_hours=1.0)
        assert result["allowed"] is False


class TestPolicyEngine:
    def test_allow_policy(self, tmp_path):
        engine = PolicyEngine(storage_dir=tmp_path)
        policy = Policy(
            name="admin-full-access",
            statements=[
                PolicyStatement(
                    sid="allow-all",
                    effect=Effect.ALLOW,
                    principals=["admin"],
                    actions=[Action.READ, Action.WRITE, Action.DEPLOY],
                    resources=["*"],
                )
            ],
        )
        engine.create_policy(policy)

        assert engine.evaluate("admin", Action.READ, "model-x") is True
        assert engine.evaluate("user1", Action.READ, "model-x") is False

    def test_deny_overrides_allow(self, tmp_path):
        engine = PolicyEngine(storage_dir=tmp_path)
        engine.create_policy(Policy(
            name="mixed",
            statements=[
                PolicyStatement(effect=Effect.ALLOW, principals=["*"], actions=[Action.READ], resources=["*"]),
                PolicyStatement(effect=Effect.DENY, principals=["blocked-user"], actions=[Action.READ], resources=["*"]),
            ],
        ))

        assert engine.evaluate("normal-user", Action.READ, "model") is True
        assert engine.evaluate("blocked-user", Action.READ, "model") is False
