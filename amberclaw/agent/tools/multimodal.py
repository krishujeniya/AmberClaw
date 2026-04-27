"""Multimodal tools for vision, audio, and documents (AC-073, AC-075, AC-076, AC-077, AC-078)."""

import base64
import mimetypes
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from amberclaw.agent.tools.base import PydanticTool
from amberclaw.providers.transcription import GroqTranscriptionProvider, OpenAITranscriptionProvider
from amberclaw.providers.tts import OpenAIttsProvider, ElevenLabsTTSProvider


class DescribeImageArgs(BaseModel):
    """Arguments for the describe_image tool."""

    path: str = Field(..., description="Local path to the image file.")
    prompt: str = Field("Describe this image in detail.", description="Question or prompt about the image.")


class VisionTool(PydanticTool):
    """
    Tool to describe or analyze an image file using multimodal LLM capabilities (AC-073).
    Note: This is useful when the agent needs to analyze a specific local file that wasn't
    automatically included in the chat context.
    """

    @property
    def name(self) -> str:
        return "describe_image"

    @property
    def description(self) -> str:
        return "Analyze a local image file and return a text description."

    @property
    def args_schema(self) -> type[DescribeImageArgs]:
        return DescribeImageArgs

    def __init__(self, provider: Any = None):
        super().__init__()
        self._provider = provider  # AgentLoop should inject the current provider

    async def run(self, args: DescribeImageArgs) -> str:
        if not self._provider:
            return "Error: No multimodal provider configured."

        p = Path(args.path)
        if not p.is_file():
            return f"Error: Image file not found: {args.path}"

        try:
            # We use the current provider's chat method to analyze the image
            # Construct a single-turn multimodal message
            raw = p.read_bytes()
            mime = mimetypes.guess_type(args.path)[0] or "image/jpeg"
            b64 = base64.b64encode(raw).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": args.prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ]

            response = await self._provider.chat(messages=messages, max_tokens=1024)
            if response.finish_reason == "error":
                return f"Error analyzing image: {response.content}"

            return response.content
        except Exception as e:
            return f"Error: {str(e)}"


class AnalyzeVideoArgs(BaseModel):
    """Arguments for the analyze_video tool."""

    path: str = Field(..., description="Path to the video file.")
    num_frames: int = Field(5, description="Number of frames to extract and analyze.")
    prompt: str = Field("Describe what happens in this video.", description="Question or prompt about the video.")


class VideoAnalysisTool(PydanticTool):
    """Tool for real-time video frame extraction and analysis (AC-077)."""

    @property
    def name(self) -> str:
        return "analyze_video"

    @property
    def description(self) -> str:
        return "Extract frames from a video and analyze them using vision capabilities."

    @property
    def args_schema(self) -> type[AnalyzeVideoArgs]:
        return AnalyzeVideoArgs

    def __init__(self, provider: Any = None):
        super().__init__()
        self._provider = provider

    async def run(self, args: AnalyzeVideoArgs) -> str:
        if not self._provider:
            return "Error: No multimodal provider configured."

        try:
            import cv2
        except ImportError:
            return "Error: 'opencv-python' (cv2) not installed."

        p = Path(args.path)
        if not p.is_file():
            return f"Error: Video file not found: {args.path}"

        try:
            cap = cv2.VideoCapture(str(p))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                return "Error: Could not read video frames."

            interval = max(1, total_frames // args.num_frames)
            frames = []

            for i in range(args.num_frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
                ret, frame = cap.read()
                if not ret:
                    break
                # Convert to JPEG base64
                _, buffer = cv2.imencode(".jpg", frame)
                b64 = base64.b64encode(buffer).decode()
                frames.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                )

            cap.release()

            if not frames:
                return "Error: Failed to extract frames."

            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": args.prompt}] + frames,
                }
            ]

            response = await self._provider.chat(messages=messages, max_tokens=1024)
            return response.content
        except Exception as e:
            return f"Error analyzing video: {str(e)}"


class CaptureSensorArgs(BaseModel):
    """Arguments for the capture_sensor tool."""

    sensor_type: Literal["webcam", "microphone"] = Field(..., description="Type of sensor to capture.")
    duration: int = Field(3, description="Duration in seconds (for microphone).")
    output_path: str = Field("capture.jpg", description="Path to save the capture.")


class SensorInputTool(PydanticTool):
    """Tool for real-time sensor inputs (AC-079)."""

    @property
    def name(self) -> str:
        return "capture_sensor"

    @property
    def description(self) -> str:
        return "Capture input from local hardware sensors like webcam or microphone."

    @property
    def args_schema(self) -> type[CaptureSensorArgs]:
        return CaptureSensorArgs

    async def run(self, args: CaptureSensorArgs) -> str:
        if args.sensor_type == "webcam":
            try:
                import cv2

                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                if not ret:
                    cap.release()
                    return "Error: Could not access webcam."
                cv2.imwrite(args.output_path, frame)
                cap.release()
                return f"Webcam image saved to {args.output_path}"
            except Exception as e:
                return f"Error capturing webcam: {str(e)}"
        elif args.sensor_type == "microphone":
            try:
                import sounddevice as sd
                from scipy.io.wavfile import write

                fs = 44100
                recording = sd.rec(int(args.duration * fs), samplerate=fs, channels=1)
                sd.wait()
                write(args.output_path, fs, recording)
                return f"Microphone audio saved to {args.output_path}"
            except Exception as e:
                return f"Error capturing microphone: {str(e)}"
        return "Error: Invalid sensor type."


class TranscribeAudioArgs(BaseModel):

    """Arguments for the transcribe_audio tool."""

    path: str = Field(..., description="Local path to the audio file.")
    provider: Literal["groq", "openai"] = Field("groq", description="Transcription provider to use.")


class TranscriptionTool(PydanticTool):
    """Tool to transcribe audio files using Whisper (AC-075)."""

    @property
    def name(self) -> str:
        return "transcribe_audio"

    @property
    def description(self) -> str:
        return "Transcribe a local audio file to text using Whisper."

    @property
    def args_schema(self) -> type[TranscribeAudioArgs]:
        return TranscribeAudioArgs

    async def run(self, args: TranscribeAudioArgs) -> str:
        p = Path(args.path)
        if not p.is_file():
            return f"Error: Audio file not found: {args.path}"

        if args.provider == "groq":
            transcriber = GroqTranscriptionProvider()
        else:
            transcriber = OpenAITranscriptionProvider()

        text = await transcriber.transcribe(p)
        if not text:
            return "Error: Transcription failed or returned empty text."

        return text


class TextToSpeechArgs(BaseModel):
    """Arguments for the speak_text tool."""

    text: str = Field(..., description="Text to convert to speech.")
    output_path: str = Field("output.mp3", description="Path to save the audio file.")
    provider: Literal["openai", "elevenlabs"] = Field("openai", description="TTS provider to use.")


class TTSTool(PydanticTool):
    """Tool for text-to-speech output (AC-076)."""

    @property
    def name(self) -> str:
        return "speak_text"

    @property
    def description(self) -> str:
        return "Convert text to speech and save as an audio file."

    @property
    def args_schema(self) -> type[TextToSpeechArgs]:
        return TextToSpeechArgs

    async def run(self, args: TextToSpeechArgs) -> str:
        if args.provider == "openai":
            provider = OpenAIttsProvider()
        else:
            provider = ElevenLabsTTSProvider()

        success = await provider.generate(args.text, args.output_path)
        if success:
            return f"Audio successfully saved to {args.output_path}"
        return "Error: TTS generation failed."


class IngestDocumentArgs(BaseModel):
    """Arguments for the ingest_document tool."""

    path: str = Field(..., description="Path to the document (PDF, Docx, etc.)")
    strategy: str = Field("auto", description="Ingestion strategy (auto, fast, ocr_only, hi_res)")


class DocumentIngestionTool(PydanticTool):
    """Tool for rich document ingestion using Unstructured (AC-078)."""

    @property
    def name(self) -> str:
        return "ingest_document"

    @property
    def description(self) -> str:
        return "Ingest a complex document (PDF, Docx, etc.) and return its content as text/markdown."

    @property
    def args_schema(self) -> type[IngestDocumentArgs]:
        return IngestDocumentArgs

    async def run(self, args: IngestDocumentArgs) -> str:
        try:
            from unstructured.partition.auto import partition

            p = Path(args.path)
            if not p.is_file():
                return f"Error: File not found: {args.path}"

            elements = partition(filename=str(p), strategy=args.strategy)
            text = "\n\n".join([str(el) for el in elements])

            if not text:
                return "Error: No content extracted from document."

            return text
        except ImportError:
            return "Error: 'unstructured' library not installed. Install with amberclaw[all]."
        except Exception as e:
            return f"Error ingesting document: {str(e)}"
