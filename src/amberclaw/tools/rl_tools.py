"""Reinforcement learning tools for trajectory recording and environment diagnostics."""

import json

from pydantic import BaseModel, Field

from amberclaw.rl.system_check import RLSystemCheck
from amberclaw.rl.trajectory import Trajectory, TrajectoryBuffer
from amberclaw.tools.registry import BaseTool

# Module-level default buffer for agent telemetry collection
_default_buffer = TrajectoryBuffer(max_size=500)


def get_default_trajectory_buffer() -> TrajectoryBuffer:
    """Retrieve shared default trajectory buffer."""
    return _default_buffer


class RecordStepArgs(BaseModel):
    """Arguments for logging an RL trajectory transition."""

    episode_id: str = Field(..., description="Unique episode or session identifier")
    action: str = Field(..., description="Action taken or tool invoked")
    reward: float = Field(
        default=0.0, description="Scalar feedback reward (-1.0 to 1.0)"
    )
    done: bool = Field(
        default=False, description="Whether this action concluded the episode"
    )
    notes: str | None = Field(default=None, description="Optional diagnostic context")


class RecordTrajectoryStepTool(BaseTool):
    """Tool allowing agents to submit experience replay transitions to the RL buffer."""

    name = "record_rl_step"
    description = "Record an action, scalar reward, and termination flag into the RL trajectory buffer."
    args_schema = RecordStepArgs

    def __init__(self, buffer: TrajectoryBuffer | None = None) -> None:
        super().__init__()
        self.buffer = buffer or get_default_trajectory_buffer()

    async def run(
        self,
        episode_id: str,
        action: str,
        reward: float = 0.0,
        done: bool = False,
        notes: str | None = None,
    ) -> str:
        """Append a step to the active episode trajectory."""
        traj: Trajectory | None = None
        for existing in self.buffer._trajectories:
            if existing.episode_id == episode_id:
                traj = existing
                break

        if traj is None:
            traj = Trajectory(episode_id=episode_id)
            self.buffer.append(traj)

        info = {"notes": notes} if notes else {}
        traj.add_step(action=action, reward=reward, done=done, state=info)

        return (
            f"Step recorded for episode '{episode_id}' (step count: {traj.length}, "
            f"current total reward: {traj.total_reward:.2f}, done: {done})"
        )


class RLDiagnosticsTool(BaseTool):
    """Tool inspecting local hardware, vLLM acceleration, and RL training readiness."""

    name = "rl_system_diagnostics"
    description = "Run diagnostic checks on local GPU memory, Ray cluster, and vLLM inference readiness."
    args_schema = None

    async def run(self, **_kwargs) -> str:
        """Run system check and return JSON diagnostics."""
        diag = RLSystemCheck.run_check()
        return json.dumps(diag.model_dump(), indent=2)


class RLBufferStatsTool(BaseTool):
    """Tool reporting trajectory replay buffer statistics."""

    name = "rl_buffer_stats"
    description = "Check the total episodes, total steps, and mean reward stored in the RL experience buffer."
    args_schema = None

    def __init__(self, buffer: TrajectoryBuffer | None = None) -> None:
        super().__init__()
        self.buffer = buffer or get_default_trajectory_buffer()

    async def run(self, **_kwargs) -> str:
        """Compute summary statistics across buffered trajectories."""
        episodes = self.buffer._trajectories
        total_episodes = len(episodes)
        total_steps = sum(t.length for t in episodes)
        total_rewards = [t.total_reward for t in episodes]
        mean_reward = (
            (sum(total_rewards) / total_episodes) if total_episodes > 0 else 0.0
        )

        stats = {
            "total_episodes": total_episodes,
            "total_steps": total_steps,
            "mean_episode_reward": round(mean_reward, 3),
            "max_capacity": self.buffer.max_size,
        }
        return json.dumps(stats, indent=2)
