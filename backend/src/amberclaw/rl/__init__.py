"""AmberClaw Reinforcement Learning (RL), GRPO training, trajectory buffer, and environments."""

from pydantic import BaseModel, Field

from amberclaw.rl.environments import (
    BaseRLEnvironment,
    CodingBenchmarkEnvironment,
    SafetyAlignmentEnvironment,
    ToolCallingEnvironment,
)
from amberclaw.rl.orchestrator import RLOrchestrator, RLProcessConfig, RLProcessType
from amberclaw.rl.system_check import RLSystemCheck, RLSystemDiagnostics
from amberclaw.rl.trainer import GRPOTrainer, GRPOTrainStepResult, RLTrainerConfig
from amberclaw.rl.trajectory import Trajectory, TrajectoryBuffer, TrajectoryStep
from amberclaw.rl.wandb_logger import RLMetricsLogger, RLStepMetric


class RLModuleConfig(BaseModel):
    """Configuration for the amberclaw.rl module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "BaseRLEnvironment",
    "CodingBenchmarkEnvironment",
    "GRPOTrainStepResult",
    "GRPOTrainer",
    "RLMetricsLogger",
    "RLModuleConfig",
    "RLOrchestrator",
    "RLProcessConfig",
    "RLProcessType",
    "RLStepMetric",
    "RLSystemCheck",
    "RLSystemDiagnostics",
    "RLTrainerConfig",
    "SafetyAlignmentEnvironment",
    "ToolCallingEnvironment",
    "Trajectory",
    "TrajectoryBuffer",
    "TrajectoryStep",
]
