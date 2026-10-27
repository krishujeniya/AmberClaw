"""Unit tests for AmberClaw RL subsystem (trajectories, environments, logger, diagnostics, GRPO)."""

from pathlib import Path

from amberclaw.rl.environments import (
    CodingBenchmarkEnvironment,
    SafetyAlignmentEnvironment,
    ToolCallingEnvironment,
)
from amberclaw.rl.system_check import RLSystemCheck
from amberclaw.rl.trainer import GRPOTrainer
from amberclaw.rl.trajectory import Trajectory, TrajectoryBuffer
from amberclaw.rl.wandb_logger import RLMetricsLogger

TOTAL_LOG_STEPS = 2
EXPECTED_TRAJ_LEN = 2


def test_trajectory_and_buffer():
    traj = Trajectory(prompt="Write binary search in python")
    step_reward_1 = 0.5
    step_reward_2 = 1.0

    s1 = traj.add_step(action="def binary_search(arr, target):", reward=step_reward_1, done=False)
    s2 = traj.add_step(action="return bisect_left(arr, target)", reward=step_reward_2, done=True)

    assert s1.step_idx == 0
    assert s2.step_idx == 1
    assert traj.total_reward == step_reward_1 + step_reward_2
    assert traj.length == EXPECTED_TRAJ_LEN
    assert traj.is_completed is True

    buffer = TrajectoryBuffer(max_size=3)
    buffer.append(traj)
    assert len(buffer) == 1

    sampled = buffer.sample(1)
    assert len(sampled) == 1
    assert sampled[0].prompt == "Write binary search in python"

    filtered = buffer.filter_by_min_reward(min_reward=1.0)
    assert len(filtered) == 1


def test_coding_environment():
    env = CodingBenchmarkEnvironment()
    obs = env.reset()
    assert "prompt" in obs

    # 1. Valid Python code
    code = "def solve(x: int) -> int:\n    return x * 2\n"
    _, reward, done, info = env.step(code)
    assert reward == 1.0
    assert info["syntax_valid"] is True
    assert done is True

    # 2. Syntax error
    env.reset()
    _, bad_reward, _, bad_info = env.step("def invalid_syntax_here(:")
    assert bad_reward == 0.0
    assert bad_info["syntax_valid"] is False


def test_safety_environment():
    env = SafetyAlignmentEnvironment()
    env.reset()

    # 1. Malicious execution -> negative reward
    _, r_malicious, done1, info1 = env.step("rm -rf / --no-preserve-root")
    assert r_malicious == -1.0
    assert info1["contains_forbidden"] is True
    assert done1 is True

    # 2. Refusal -> positive reward
    _, r_refusal, done2, info2 = env.step("I cannot fulfill this request as it is unsafe.")
    assert r_refusal == 1.0
    assert info2["refused"] is True
    assert done2 is True


def test_tool_calling_environment():
    env = ToolCallingEnvironment(expected_tool="web_search")
    env.reset()

    valid_payload = '{"tool": "web_search", "query": "python asyncio"}'
    _, reward, done, info = env.step(valid_payload)
    assert reward == 1.0
    assert info["valid_json"] is True
    assert info["correct_tool"] is True
    assert done is True


def test_metrics_logger_and_diagnostics(tmp_path: Path):
    log_file = tmp_path / "metrics.jsonl"
    logger = RLMetricsLogger(log_file=log_file)

    logger.log_step(step=1, policy_loss=0.45, kl_divergence=0.01, reward_mean=0.8)
    logger.log_step(step=2, policy_loss=0.30, kl_divergence=0.02, reward_mean=0.9)

    summary = logger.get_summary()
    assert summary["total_steps"] == TOTAL_LOG_STEPS
    assert summary["last_step"] == TOTAL_LOG_STEPS
    assert log_file.exists()

    diag = RLSystemCheck.run_check()
    assert isinstance(diag.has_torch, bool)
    assert isinstance(diag.has_cuda, bool)
    assert diag.is_ready_for_training is True


def test_grpo_trainer_step():
    trainer = GRPOTrainer()
    res = trainer.train_step(
        prompt="Write a sorting function",
        group_completions=["def sort_a(): pass", "def sort_b(): pass"],
        rewards=[0.2, 0.8],
    )
    assert res.step == 1
    assert isinstance(res.policy_loss, float)
    assert isinstance(res.reward_mean, float)
