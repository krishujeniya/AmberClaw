"""
AmberClaw multimodal module for processing images, videos, audio, screen sharing, and vision LLM routing.
"""

from pydantic import BaseModel, Field

from amberclaw.multimodal.audio import AudioSummarizer, AudioSummaryResult, AudioTopic
from amberclaw.multimodal.image import ImageMetadata, ImageProcessor
from amberclaw.multimodal.router import AttachmentMedia, MultimodalRouter
from amberclaw.multimodal.screenshare import (
    ScreenAnalysisResult,
    ScreenFrameSample,
    ScreenShareSession,
)
from amberclaw.multimodal.video import VideoMetadata, VideoProcessor


class MultimodalModuleConfig(BaseModel):
    """Configuration for the amberclaw.multimodal module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "AttachmentMedia",
    "AudioSummarizer",
    "AudioSummaryResult",
    "AudioTopic",
    "ImageMetadata",
    "ImageProcessor",
    "MultimodalModuleConfig",
    "MultimodalRouter",
    "ScreenAnalysisResult",
    "ScreenFrameSample",
    "ScreenShareSession",
    "VideoMetadata",
    "VideoProcessor",
]
