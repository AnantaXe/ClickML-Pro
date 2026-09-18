"""
Access-control policies for models.

Defines who (users, teams, roles) can perform operations (read, deploy,
delete, promote) on which models. Policies are stored as JSON documents
and evaluated at request time.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    DEPLOY = "deploy"
    PROMOTE = "promote"
    QUANTIZE = "quantize"
    TRAIN = "train"


class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicyStatement(BaseModel):
    """Single allow/deny rule."""

    sid: str = ""
    effect: Effect = Effect.ALLOW
    principals: list[str] = Field(default_factory=list)  # user/team IDs or "*"
    actions: list[Action] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)  # model names / patterns or "*"
    conditions: dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    """A named policy document containing one or more statements."""

    name: str
    description: str = ""
    statements: list[PolicyStatement] = Field(default_factory=list)
    version: str = "2024-01-01"


class PolicyEngine:
    """Evaluate access-control policies."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            from clickml_pro.config.settings import get_settings
            storage_dir = Path(get_settings().data_dir) / "governance" / "policies"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._policies: dict[str, Policy] = {}
        self._load_all()

    # ── CRUD ────────────────────────────────────────────────────────────

    def create_policy(self, policy: Policy) -> None:
        self._policies[policy.name] = policy
        self._save(policy)
        logger.info("Policy created: %s", policy.name)

    def get_policy(self, name: str) -> Policy | None:
        return self._policies.get(name)

    def list_policies(self) -> list[Policy]:
        return list(self._policies.values())

    def delete_policy(self, name: str) -> bool:
        if name not in self._policies:
            return False
        del self._policies[name]
        path = self.storage_dir / f"{name}.json"
        if path.exists():
            path.unlink()
        logger.info("Policy deleted: %s", name)
        return True

    # ── evaluation ──────────────────────────────────────────────────────

    def evaluate(
        self,
        principal: str,
        action: Action,
        resource: str,
    ) -> bool:
        """Return True if the request is allowed, False otherwise.

        Default-deny: if no statement explicitly allows the action, it is denied.
        An explicit DENY overrides any ALLOW.
        """
        allowed = False

        for policy in self._policies.values():
            for stmt in policy.statements:
                if not self._matches_principal(stmt.principals, principal):
                    continue
                if not self._matches_action(stmt.actions, action):
                    continue
                if not self._matches_resource(stmt.resources, resource):
                    continue

                if stmt.effect == Effect.DENY:
                    logger.debug(
                        "DENY  principal=%s action=%s resource=%s  by policy=%s sid=%s",
                        principal, action.value, resource, policy.name, stmt.sid,
                    )
                    return False

                if stmt.effect == Effect.ALLOW:
                    allowed = True

        if allowed:
            logger.debug(
                "ALLOW  principal=%s action=%s resource=%s",
                principal, action.value, resource,
            )
        return allowed

    # ── matching helpers ────────────────────────────────────────────────

    @staticmethod
    def _matches_principal(patterns: list[str], principal: str) -> bool:
        if "*" in patterns:
            return True
        return principal in patterns

    @staticmethod
    def _matches_action(patterns: list[Action], action: Action) -> bool:
        if not patterns:
            return True  # no restriction → matches all
        return action in patterns

    @staticmethod
    def _matches_resource(patterns: list[str], resource: str) -> bool:
        if "*" in patterns or not patterns:
            return True
        for p in patterns:
            if p == resource:
                return True
            # Simple prefix-wildcard:  "model/*" matches "model/gpt4"
            if p.endswith("/*") and resource.startswith(p[:-2]):
                return True
        return False

    # ── persistence ─────────────────────────────────────────────────────

    def _save(self, policy: Policy) -> None:
        path = self.storage_dir / f"{policy.name}.json"
        path.write_text(policy.model_dump_json(indent=2))

    def _load_all(self) -> None:
        for path in self.storage_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text())
                policy = Policy(**raw)
                self._policies[policy.name] = policy
            except Exception as exc:
                logger.warning("Failed to load policy %s: %s", path.name, exc)
