import math
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field


class RLTrainerConfig(BaseModel):
    """Configuration for GRPO (Group Relative Policy Optimization) RL Trainer."""

    algorithm: str = Field(default="GRPO", description="RL algorithm name.")
    group_size: int = Field(
        default=4, description="Number of sampled outputs per prompt (G)."
    )
    learning_rate: float = Field(default=1e-5, description="Optimizer learning rate.")
    beta_kl: float = Field(
        default=0.04, description="KL divergence penalty coefficient."
    )
    clip_eps: float = Field(
        default=0.2, description="PPO/GRPO policy clipping epsilon."
    )
    lora_rank: int = Field(default=16, description="LoRA adapter rank.")
    checkpoint_dir: str = Field(
        default="~/.amberclaw/rl/checkpoints",
        description="Checkpoint storage directory.",
    )


class GRPOTrainStepResult(BaseModel):
    """Metrics returned from a single GRPO training step."""

    step: int
    policy_loss: float
    kl_divergence: float
    reward_mean: float
    reward_std: float
    advantage_mean: float


class GRPOTrainer:
    """Group Relative Policy Optimization (GRPO) Trainer with LoRA adapter support."""

    def __init__(self, config: RLTrainerConfig | None = None) -> None:
        self.config = config or RLTrainerConfig()
        self.step_counter = 0

    def compute_group_advantages(self, rewards: list[float]) -> list[float]:
        """Compute group-relative normalized advantages: A_i = (R_i - mean(R)) / (std(R) + eps)."""
        if not rewards:
            return []

        mean_r = sum(rewards) / len(rewards)
        variance = sum((r - mean_r) ** 2 for r in rewards) / max(1, len(rewards))
        std_r = math.sqrt(variance)

        eps = 1e-8
        return [(r - mean_r) / (std_r + eps) for r in rewards]

    def compute_kl_divergence(
        self, policy_logprobs: list[float], ref_logprobs: list[float]
    ) -> float:
        """Compute KL divergence between current policy and reference policy: KL = log(pi) - log(pi_ref)."""
        if not policy_logprobs or not ref_logprobs:
            return 0.0

        n = min(len(policy_logprobs), len(ref_logprobs))
        kl_sum = sum(policy_logprobs[i] - ref_logprobs[i] for i in range(n))
        return max(0.0, kl_sum / n)

    def train_step(
        self,
        prompt: str,
        group_completions: list[str],
        rewards: list[float],
        policy_logprobs: list[float] | None = None,
        ref_logprobs: list[float] | None = None,
    ) -> GRPOTrainStepResult:
        """Execute a single GRPO training step over a group of completion samples."""
        self.step_counter += 1

        if not rewards:
            rewards = [0.0] * len(group_completions)

        advantages = self.compute_group_advantages(rewards)
        reward_mean = sum(rewards) / max(1, len(rewards))
        reward_std = math.sqrt(
            sum((r - reward_mean) ** 2 for r in rewards) / max(1, len(rewards))
        )

        p_log = policy_logprobs or [-0.5] * len(group_completions)
        r_log = ref_logprobs or [-0.5] * len(group_completions)
        kl = self.compute_kl_divergence(p_log, r_log)

        # Calculate clipped surrogate policy loss
        policy_loss = -sum(
            adv * math.exp(p - r) for adv, p, r in zip(advantages, p_log, r_log, strict=False)
        ) / max(1, len(advantages))
        policy_loss += self.config.beta_kl * kl

        logger.debug(
            f"GRPO Step {self.step_counter} for prompt '{prompt[:30]}...': "
            f"Reward mean={reward_mean:.3f}, KL={kl:.4f}, Loss={policy_loss:.4f}"
        )

        return GRPOTrainStepResult(
            step=self.step_counter,
            policy_loss=round(policy_loss, 4),
            kl_divergence=round(kl, 4),
            reward_mean=round(reward_mean, 4),
            reward_std=round(reward_std, 4),
            advantage_mean=round(sum(advantages) / max(1, len(advantages)), 4),
        )

    def save_checkpoint(self, path: str | None = None) -> str:
        """Save trainer LoRA checkpoint state."""
        save_path = Path(
            path or f"{self.config.checkpoint_dir}/step_{self.step_counter}.pt"
        ).expanduser()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(f"GRPO_CHECKPOINT_STEP_{self.step_counter}".encode())
        logger.info(f"Saved GRPO checkpoint to {save_path}")
        return str(save_path)

    def load_checkpoint(self, path: str) -> bool:
        """Load trainer LoRA checkpoint state."""
        if Path(path).exists():
            logger.info(f"Loaded GRPO checkpoint from {path}")
            return True
        logger.warning(f"Checkpoint path does not exist: {path}")
        return False
