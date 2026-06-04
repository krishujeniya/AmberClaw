"""Unit tests for local vLLM runner and configuration options."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

from amberclaw.providers.vllm import VLLMLocalRunner, VLLMProvider
from amberclaw.config.schema import Config, ProviderConfig


def test_vllm_runner_argument_builder():
    # Scenario 1: Basic setup
    runner = VLLMLocalRunner(
        model="Qwen/Qwen2.5-7B-Instruct",
        api_base="http://localhost:8000/v1",
    )
    assert runner.host == "localhost"
    assert runner.port == 8000
    assert runner.is_local_base() is True

    args = runner.build_command_args(use_binary=False)
    assert args == [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        "Qwen/Qwen2.5-7B-Instruct",
        "--host",
        "localhost",
        "--port",
        "8000",
    ]

    # Scenario 2: Quantization and Speculative Decoding
    runner_adv = VLLMLocalRunner(
        model="Qwen/Qwen2.5-7B-Instruct",
        api_base="http://127.0.0.1:9090/v1",
        quantization="awq",
        speculative_model="Qwen/Qwen2.5-1.5B-Instruct",
        num_speculative_tokens=5,
    )
    assert runner_adv.host == "127.0.0.1"
    assert runner_adv.port == 9090
    assert runner_adv.is_local_base() is True

    args_adv = runner_adv.build_command_args(use_binary=False)
    assert "--quantization" in args_adv
    assert args_adv[args_adv.index("--quantization") + 1] == "awq"
    assert "--speculative-model" in args_adv
    assert args_adv[args_adv.index("--speculative-model") + 1] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert "--num-speculative-tokens" in args_adv
    assert args_adv[args_adv.index("--num-speculative-tokens") + 1] == "5"

    # Scenario 3: Binary mode (vllm serve)
    args_bin = runner_adv.build_command_args(use_binary=True)
    assert args_bin[0] == "vllm"
    assert args_bin[1] == "serve"
    assert args_bin[2] == "Qwen/Qwen2.5-7B-Instruct"


@pytest.mark.asyncio
async def test_vllm_runner_lifecycle():
    runner = VLLMLocalRunner(
        model="Qwen/Qwen2.5-7B-Instruct",
        api_base="http://localhost:8000/v1",
        quantization="fp8",
    )

    mock_process = AsyncMock()
    mock_process.terminate = MagicMock()
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        await runner.start()
        
        mock_exec.assert_called_once()
        called_args = mock_exec.call_args[0]
        assert called_args[0] == "python"
        assert "--quantization" in called_args
        assert called_args[called_args.index("--quantization") + 1] == "fp8"

        # Test stop
        await runner.stop()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()


@pytest.mark.asyncio
async def test_vllm_runner_health_checks():
    runner = VLLMLocalRunner(
        model="Qwen/Qwen2.5-7B-Instruct",
        api_base="http://localhost:8000/v1",
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock healthy response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        healthy = await runner.check_health()
        assert healthy is True
        mock_get.assert_called_with("http://localhost:8000/health")

        # Mock exception
        mock_get.side_effect = Exception("connection refused")
        unhealthy = await runner.check_health()
        assert unhealthy is False
