"""Experiment tracking and metrics logging for Reinforcement Learning training runs."""

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RLStepMetric(BaseModel):
    """Container for metrics recorded at a single RL step."""

    step: int
    timestamp: float = Field(default_factory=time.time)
    policy_loss: float
    kl_divergence: float
    reward_mean: float
    reward_std: float = 0.0
    advantage_mean: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)


class RLMetricsLogger:
    """Logs RL training metrics to in-memory buffers and optional local JSONL logs."""

    def __init__(
        self,
        experiment_name: str = "amberclaw-grpo",
        log_file: Path | str | None = None,
        use_wandb: bool = False,
    ) -> None:
        self.experiment_name = experiment_name
        self.log_file = Path(log_file) if log_file else None
        self.use_wandb = use_wandb
        self.history: list[RLStepMetric] = []

        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_step(
        self,
        step: int,
        policy_loss: float,
        kl_divergence: float,
        reward_mean: float,
        extra_metrics: dict[str, Any] | None = None,
    ) -> RLStepMetric:
        """Record and persist a training step metric."""
        extra = extra_metrics or {}
        metric = RLStepMetric(
            step=step,
            policy_loss=policy_loss,
            kl_divergence=kl_divergence,
            reward_mean=reward_mean,
            reward_std=extra.get("reward_std", 0.0),
            advantage_mean=extra.get("advantage_mean", 0.0),
            extra=extra,
        )
        self.history.append(metric)

        if self.log_file:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(metric.model_dump()) + "\n")

        return metric

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregate metrics across the full run history."""
        if not self.history:
            return {"total_steps": 0}

        avg_loss = sum(m.policy_loss for m in self.history) / len(self.history)
        avg_reward = sum(m.reward_mean for m in self.history) / len(self.history)
        avg_kl = sum(m.kl_divergence for m in self.history) / len(self.history)

        return {
            "total_steps": len(self.history),
            "average_policy_loss": round(avg_loss, 4),
            "average_reward_mean": round(avg_reward, 4),
            "average_kl_divergence": round(avg_kl, 4),
            "last_step": self.history[-1].step,
        }
