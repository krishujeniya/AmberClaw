# ruff: noqa: PLR2004, RUF059
"""Unit tests for AmberClaw Reinforcement Learning environments, buffer, and diagnostics."""

from amberclaw.rl.environments import (
    CodingBenchmarkEnvironment,
    SafetyAlignmentEnvironment,
    ToolCallingEnvironment,
)
from amberclaw.rl.system_check import RLSystemCheck
from amberclaw.rl.trajectory import Trajectory, TrajectoryBuffer

# ==============================================================================
# 1. Coding Benchmark Environment
# ==============================================================================


def test_coding_environment_syntax_and_keywords():
    env = CodingBenchmarkEnvironment()
    obs = env.reset()
    assert obs["step"] == 0
    assert "task" in obs

    # Step with valid Python function with def and return
    code = "def multiply(x, y):\n    return x * y"
    obs, reward, done, info = env.step(code)
    assert reward == 1.0
    assert info["syntax_valid"] is True
    assert done is True


def test_coding_environment_syntax_error():
    env = CodingBenchmarkEnvironment()
    env.reset()

    # Step with invalid syntax
    invalid_code = "def syntax_error( x: return"
    obs, reward, done, info = env.step(invalid_code)
    assert reward == 0.0
    assert info["syntax_valid"] is False


# ==============================================================================
# 2. Safety Alignment Environment
# ==============================================================================


def test_safety_environment_adversarial_rejection():
    env = SafetyAlignmentEnvironment()
    obs = env.reset()
    assert obs["is_adversarial"] is True

    # Action complies with dangerous command -> negative reward
    obs, reward, done, info = env.step("Running rm -rf / now")
    assert reward == -1.0
    assert info["contains_forbidden"] is True
    assert done is True

    # Action refuses safely -> positive reward
    obs, reward, done, info = env.step(
        "I cannot perform destructive actions as it is prohibited."
    )
    assert reward == 1.0
    assert info["refused"] is True
    assert done is True


# ==============================================================================
# 3. Tool Calling Environment
# ==============================================================================


def test_tool_calling_environment():
    env = ToolCallingEnvironment(expected_tool="web_search")
    obs = env.reset()
    assert "available_tools" in obs

    # Step with valid JSON matching expected tool
    valid_payload = '{"tool": "web_search", "query": "python asyncio"}'
    obs, reward, done, info = env.step(valid_payload)
    assert reward == 1.0
    assert info["valid_json"] is True
    assert info["correct_tool"] is True

    # Step with valid JSON but wrong tool
    wrong_tool_payload = '{"tool": "read_file", "path": "test.txt"}'
    obs, reward, done, info = env.step(wrong_tool_payload)
    assert reward == 0.4
    assert info["valid_json"] is True
    assert info["correct_tool"] is False

    # Step with invalid JSON
    obs, reward, done, info = env.step("not valid json at all")
    assert reward == 0.0
    assert info["valid_json"] is False


# ==============================================================================
# 4. Trajectory & Experience Buffer
# ==============================================================================


def test_trajectory_accumulation_and_reward():
    traj = Trajectory(prompt="Implement bubble sort")
    assert traj.total_reward == 0.0
    assert traj.length == 0
    assert traj.is_completed is False

    traj.add_step(action="def bubble_sort(arr):", reward=0.5, done=False)
    traj.add_step(action="    return sorted(arr)", reward=1.0, done=True)

    assert traj.length == 2
    assert traj.total_reward == 1.5
    assert traj.is_completed is True


def test_trajectory_buffer_capacity_and_sampling():
    buffer = TrajectoryBuffer(max_size=3)
    assert len(buffer) == 0

    t1 = Trajectory()
    t1.add_step("a1", reward=1.0)
    t2 = Trajectory()
    t2.add_step("a2", reward=2.0)
    t3 = Trajectory()
    t3.add_step("a3", reward=3.0)
    t4 = Trajectory()
    t4.add_step("a4", reward=4.0)

    buffer.append(t1)
    buffer.append(t2)
    buffer.append(t3)
    assert len(buffer) == 3

    # Adding 4th should evict t1 (oldest)
    buffer.append(t4)
    assert len(buffer) == 3
    sample = buffer.sample(3)
    assert [t.total_reward for t in sample] == [2.0, 3.0, 4.0]

    # Filter by minimum reward
    high_reward = buffer.filter_by_min_reward(3.0)
    assert len(high_reward) == 2

    # Clear
    buffer.clear()
    assert len(buffer) == 0


# ==============================================================================
# 5. RL System Check Diagnostics
# ==============================================================================


def test_rl_system_diagnostics():
    diagnostics = RLSystemCheck.run_check()
    assert hasattr(diagnostics, "has_torch")
    assert hasattr(diagnostics, "has_cuda")
    assert hasattr(diagnostics, "recommended_device")
    assert diagnostics.recommended_device in {"cpu", "cuda", "mps"}
