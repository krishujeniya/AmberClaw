from amberclaw.rl.trainer import GRPOTrainer, GRPOTrainStepResult, RLTrainerConfig


def test_grpo_advantage_computation():
    trainer = GRPOTrainer()
    rewards = [1.0, 2.0, 3.0, 4.0]
    advantages = trainer.compute_group_advantages(rewards)

    assert len(advantages) == 4
    # Mean of normalized advantages should be ~0.0
    assert abs(sum(advantages) / 4) < 1e-5
    # Relative ordering preserved
    assert advantages[0] < advantages[1] < advantages[2] < advantages[3]


def test_grpo_kl_divergence():
    trainer = GRPOTrainer()
    p_log = [-0.2, -0.4, -0.1]
    r_log = [-0.5, -0.5, -0.5]

    kl = trainer.compute_kl_divergence(p_log, r_log)
    assert kl >= 0.0


def test_grpo_train_step():
    config = RLTrainerConfig(group_size=3)
    trainer = GRPOTrainer(config)

    prompt = "Write a Python function to compute factorial."
    completions = [
        "def fact(n): return 1 if n<=1 else n*fact(n-1)",
        "def fact(n): pass",
        "invalid python code snippet",
    ]
    rewards = [1.0, 0.2, -0.8]

    result = trainer.train_step(prompt, completions, rewards)

    assert isinstance(result, GRPOTrainStepResult)
    assert result.step == 1
    assert result.reward_mean > 0.0
    assert result.reward_std > 0.0


def test_grpo_checkpoint():
    trainer = GRPOTrainer()
    checkpoint_path = trainer.save_checkpoint("/tmp/test_grpo_ckpt.pt")
    assert checkpoint_path == "/tmp/test_grpo_ckpt.pt"

    loaded = trainer.load_checkpoint("/tmp/test_grpo_ckpt.pt")
    assert loaded is True
