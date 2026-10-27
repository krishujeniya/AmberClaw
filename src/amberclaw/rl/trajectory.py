"""Trajectory representations and experience replay buffer for Reinforcement Learning."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    """A single decision step within an RL rollout."""

    step_idx: int = Field(default=0, description="Step index within the trajectory.")
    state: dict[str, Any] = Field(default_factory=dict, description="State / observation at step.")
    action: str = Field(..., description="Action or generated completion token sequence.")
    reward: float = Field(default=0.0, description="Scalar reward received for this action.")
    done: bool = Field(default=False, description="Whether this step terminated the episode.")
    logprob: float | None = Field(default=None, description="Log probability of generated action.")
    info: dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata.")


class Trajectory(BaseModel):
    """A full episode rollout containing sequential state-action-reward steps."""

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str = Field(default="", description="Initial system prompt or user task query.")
    steps: list[TrajectoryStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_reward(self) -> float:
        """Sum of all step rewards."""
        return sum(s.reward for s in self.steps)

    @property
    def length(self) -> int:
        """Number of steps in the trajectory."""
        return len(self.steps)

    @property
    def is_completed(self) -> bool:
        """True if any step reached done=True."""
        return any(s.done for s in self.steps)

    def add_step(
        self,
        action: str,
        reward: float = 0.0,
        done: bool = False,
        state: dict[str, Any] | None = None,
        logprob: float | None = None,
    ) -> TrajectoryStep:
        """Append a new step to the episode trajectory."""
        step = TrajectoryStep(
            step_idx=len(self.steps),
            state=state or {},
            action=action,
            reward=reward,
            done=done,
            logprob=logprob,
        )
        self.steps.append(step)
        return step


class TrajectoryBuffer:
    """In-memory experience buffer storing rollouts for policy optimization."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._trajectories: list[Trajectory] = []

    def __len__(self) -> int:
        return len(self._trajectories)

    def append(self, trajectory: Trajectory) -> None:
        """Add a trajectory to the buffer, evicting oldest if capacity exceeded."""
        self._trajectories.append(trajectory)
        if len(self._trajectories) > self.max_size:
            self._trajectories.pop(0)

    def sample(self, count: int) -> list[Trajectory]:
        """Return the most recent count trajectories."""
        if count <= 0:
            return []
        return self._trajectories[-count:]

    def filter_by_min_reward(self, min_reward: float) -> list[Trajectory]:
        """Filter trajectories with cumulative reward >= min_reward."""
        return [t for t in self._trajectories if t.total_reward >= min_reward]

    def clear(self) -> None:
        """Clear all stored trajectories."""
        self._trajectories.clear()
