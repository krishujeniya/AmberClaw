from amberclaw.agent.emotion import (
    EmotionEngine,
    TextSentimentAnalyzer,
    VoiceToneAnalyzer,
)


def test_text_sentiment_analyzer():
    analyzer = TextSentimentAnalyzer()

    pos_score, pos_emo = analyzer.analyze("This is a great and wonderful experience!")
    assert pos_score > 0
    assert pos_emo == "joy"

    neg_score, neg_emo = analyzer.analyze("This is bad, terrible and horrible.")
    assert neg_score < 0
    assert neg_emo in ("sadness", "anger")

    neu_score, neu_emo = analyzer.analyze("The table is green.")
    assert neu_score == 0.0
    assert neu_emo == "neutral"


def test_voice_tone_analyzer():
    analyzer = VoiceToneAnalyzer()

    # Silence PCM
    silence_pcm = b"\x00\x00" * 1600
    low_arousal = analyzer.analyze_pcm(silence_pcm)
    assert low_arousal == 0.0

    # High energy audio PCM
    import math
    import struct

    high_pcm = bytearray()
    for i in range(1600):
        val = int(25000 * math.sin(2 * math.pi * 440 * i / 16000))
        high_pcm.extend(struct.pack("<h", val))

    high_arousal = analyzer.analyze_pcm(bytes(high_pcm))
    assert high_arousal > 0.5


def test_emotion_engine_adaptation():
    engine = EmotionEngine()

    state, adaptation = engine.process(
        text="Help! My server is broken and critical ASAP!"
    )
    assert adaptation.urgency in ("high", "critical")
    assert adaptation.tone == "direct"
    assert "concise" in adaptation.verbosity
    assert "EMOTION ADAPTATION" in adaptation.system_prompt_nudge

    state_happy, adapt_happy = engine.process(text="Thank you so much, awesome work!")
    assert state_happy.sentiment > 0
    assert adapt_happy.tone == "encouraging"
