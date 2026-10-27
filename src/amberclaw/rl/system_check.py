"""Hardware and environment diagnostics for local Reinforcement Learning training."""

import importlib.util
import shutil
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class RLSystemDiagnostics(BaseModel):
    """Diagnostic report of host machine capabilities for local RL training."""

    has_torch: bool
    has_cuda: bool
    has_mps: bool = False
    has_peft: bool = False
    gpu_name: str | None = None
    vram_gb: float | None = None
    recommended_device: str = "cpu"
    is_ready_for_training: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class RLSystemCheck:
    """Diagnoses host environment for RL training suitability."""

    @staticmethod
    def run_check() -> RLSystemDiagnostics:
        """Inspect PyTorch, CUDA acceleration, and LoRA/PEFT readiness."""
        has_torch = importlib.util.find_spec("torch") is not None
        has_peft = importlib.util.find_spec("peft") is not None

        has_cuda = False
        has_mps = False
        gpu_name = None
        vram_gb = None
        recommended_device = "cpu"

        if has_torch:
            try:
                torch_mod = importlib.import_module("torch")
                if torch_mod.cuda.is_available():
                    has_cuda = True
                    gpu_name = torch_mod.cuda.get_device_name(0)
                    vram_gb = round(torch_mod.cuda.get_device_properties(0).total_memory / (1024**3), 2)
                    recommended_device = "cuda"
                elif hasattr(torch_mod.backends, "mps") and torch_mod.backends.mps.is_available():
                    has_mps = True
                    recommended_device = "mps"
            except Exception as e:
                logger.debug(f"Torch inspection notice: {e}")

        has_nvidia_smi = shutil.which("nvidia-smi") is not None

        return RLSystemDiagnostics(
            has_torch=has_torch,
            has_cuda=has_cuda,
            has_mps=has_mps,
            has_peft=has_peft,
            gpu_name=gpu_name,
            vram_gb=vram_gb,
            recommended_device=recommended_device,
            is_ready_for_training=True,  # Training can always run in CPU/mock mode
            details={
                "nvidia_smi_present": has_nvidia_smi,
            },
        )
