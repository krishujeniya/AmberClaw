import math
import struct

from pydantic import BaseModel, Field


class EmotionState(BaseModel):
    """Unified emotional state inferred from text, voice, and visual inputs."""

    sentiment: float = Field(
        default=0.0, description="Sentiment polarity score (-1.0 to +1.0)."
    )
    arousal: float = Field(
        default=0.5, description="Emotional arousal/energy level (0.0 to 1.0)."
    )
    valence: float = Field(
        default=0.5, description="Emotional valence/positivity level (0.0 to 1.0)."
    )
    dominant_emotion: str = Field(
        default="neutral",
        description="Dominant emotion label (joy, anger, sadness, fear, neutral).",
    )
    confidence: float = Field(
        default=1.0, description="Confidence level of inference (0.0 to 1.0)."
    )


class PersonalityAdaptation(BaseModel):
    """Agent personality adaptation parameters derived from user emotion."""

    urgency: str = Field(
        default="normal",
        description="Urgency mode ('low', 'normal', 'high', 'critical').",
    )
    tone: str = Field(
        default="empathetic",
        description="Response tone ('neutral', 'empathetic', 'calming', 'encouraging', 'direct').",
    )
    verbosity: str = Field(
        default="standard",
        description="Response verbosity ('concise', 'standard', 'detailed').",
    )
    system_prompt_nudge: str = Field(
        default="", description="Prompt injection string to steer LLM style."
    )


class TextSentimentAnalyzer:
    """Rule-based and lexicon sentiment and emotion analyzer."""

    def __init__(self):
        self._positive_words = {
            "good",
            "great",
            "awesome",
            "excellent",
            "happy",
            "love",
            "thanks",
            "helpful",
            "wonderful",
        }
        self._negative_words = {
            "bad",
            "terrible",
            "awful",
            "horrible",
            "sad",
            "hate",
            "angry",
            "broken",
            "fail",
            "error",
        }
        self._urgent_words = {
            "urgent",
            "immediately",
            "help",
            "emergency",
            "broken",
            "critical",
            "asap",
        }

    def analyze(self, text: str) -> tuple[float, str]:
        """Analyze text and return (sentiment_score, dominant_emotion)."""
        if not text.strip():
            return 0.0, "neutral"

        words = [w.strip().lower() for w in text.split()]
        pos_count = sum(1 for w in words if w in self._positive_words)
        neg_count = sum(1 for w in words if w in self._negative_words)
        urgent_count = sum(1 for w in words if w in self._urgent_words)

        total = pos_count + neg_count
        if total == 0:
            score = 0.0
        else:
            score = (pos_count - neg_count) / total

        if urgent_count > 0 or neg_count > 2:
            emotion = "anger" if neg_count > pos_count else "fear"
        elif pos_count > neg_count:
            emotion = "joy"
        elif neg_count > pos_count:
            emotion = "sadness"
        else:
            emotion = "neutral"

        return score, emotion


class VoiceToneAnalyzer:
    """Arousal and energy heuristics analyzer for raw PCM audio chunks."""

    def analyze_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> float:
        """Calculate energy/arousal score (0.0 to 1.0) from raw PCM audio."""
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.5

        try:
            samples = struct.unpack(f"<{count}h", pcm_bytes)
            rms = math.sqrt(sum(float(s) * s for s in samples) / count)
            # Normalize RMS to 0.0 - 1.0 range (assuming max RMS ~ 10000)
            arousal = min(1.0, max(0.0, rms / 8000.0))
            return arousal
        except Exception:
            return 0.5


class FacialExpressionAnalyzer:
    """Stub interface for camera-based facial emotion detection."""

    def analyze_frame(self, frame_bytes: bytes) -> str:
        """Stub method for frame emotion analysis."""
        return "neutral"


class EmotionEngine:
    """Engine for fusing text, voice, and visual signals to adapt agent behavior."""

    def __init__(self):
        self.text_analyzer = TextSentimentAnalyzer()
        self.voice_analyzer = VoiceToneAnalyzer()
        self.face_analyzer = FacialExpressionAnalyzer()

    def process(
        self,
        text: str = "",
        pcm_audio: bytes | None = None,
        video_frame: bytes | None = None,
    ) -> tuple[EmotionState, PersonalityAdaptation]:
        """Fuse multimodal signals and produce unified EmotionState + PersonalityAdaptation."""
        sentiment_score, text_emotion = self.text_analyzer.analyze(text)

        arousal = 0.5
        if pcm_audio:
            arousal = self.voice_analyzer.analyze_pcm(pcm_audio)

        face_emotion = "neutral"
        if video_frame:
            face_emotion = self.face_analyzer.analyze_frame(video_frame)

        dominant = text_emotion if text_emotion != "neutral" else face_emotion
        valence = max(0.0, min(1.0, (sentiment_score + 1.0) / 2.0))

        state = EmotionState(
            sentiment=sentiment_score,
            arousal=arousal,
            valence=valence,
            dominant_emotion=dominant,
            confidence=0.85,
        )

        adaptation = self.adapt_personality(state, text=text)
        return state, adaptation

    def adapt_personality(
        self, state: EmotionState, text: str = ""
    ) -> PersonalityAdaptation:
        """Derive personality adaptation rules based on detected emotion."""
        words = [w.strip().lower() for w in text.split()]
        is_urgent = any(
            w in {"urgent", "emergency", "asap", "broken", "help"} for w in words
        )

        if is_urgent or state.arousal > 0.8:
            urgency = "critical" if is_urgent else "high"
            tone = "direct"
            verbosity = "concise"
            nudge = "[EMOTION ADAPTATION: User is stressed/urgent. Respond concisely, directly, and offer immediate assistance without fluff.]"
        elif state.dominant_emotion in ("sadness", "fear") or state.sentiment < -0.3:
            urgency = "normal"
            tone = "empathetic"
            verbosity = "standard"
            nudge = "[EMOTION ADAPTATION: User expresses negative emotion. Adopt an empathetic, supportive, and reassuring tone.]"
        elif state.dominant_emotion == "joy" or state.sentiment > 0.3:
            urgency = "normal"
            tone = "encouraging"
            verbosity = "standard"
            nudge = "[EMOTION ADAPTATION: User is upbeat. Maintain an enthusiastic, encouraging tone.]"
        else:
            urgency = "normal"
            tone = "neutral"
            verbosity = "standard"
            nudge = ""

        return PersonalityAdaptation(
            urgency=urgency,
            tone=tone,
            verbosity=verbosity,
            system_prompt_nudge=nudge,
        )
