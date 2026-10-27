import pytest

from amberclaw.multimodal.audio import AudioSummarizer, AudioSummaryResult
from amberclaw.voice.stt import SpeechToTextEngine, STTConfig


@pytest.mark.asyncio
async def test_audio_summarizer():
    stt = SpeechToTextEngine(STTConfig(provider="simulated"))
    summarizer = AudioSummarizer(stt_engine=stt)

    # 5 seconds of PCM audio (16000 Hz, 16-bit mono)
    sample_pcm = b"\x00\x00" * (16000 * 5)
    result = await summarizer.summarize_audio(sample_pcm, title="Weekly Team Sync")

    assert isinstance(result, AudioSummaryResult)
    assert result.title == "Weekly Team Sync"
    assert result.duration_sec == 5.0
    assert len(result.executive_summary) > 0
    assert len(result.action_items) >= 1
    assert len(result.topics) >= 1


def test_generate_summary_from_transcript():
    summarizer = AudioSummarizer()
    raw_text = "Alice: We completed the security audit.\nBob: I will deploy the patches tomorrow."
    result = summarizer.generate_summary_from_transcript(
        raw_text, title="Sprint Retrospective"
    )

    assert result.title == "Sprint Retrospective"
    assert result.raw_transcript == raw_text
    assert len(result.action_items) > 0
