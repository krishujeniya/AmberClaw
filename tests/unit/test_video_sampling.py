"""Frame sampling must honor the requested rate and release capture resources."""

import sys
from types import SimpleNamespace

import pytest

from amberclaw.multimodal.video import VideoProcessor


def test_sampling_rate_limits_frame_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    class Capture:
        def __init__(self) -> None:
            self.positions: list[int] = []
            self.released = False

        def isOpened(self) -> bool:  # noqa: N802 - OpenCV capture protocol
            return not self.released

        def get(self, key: str) -> int:
            return 100 if key == "count" else 10

        def set(self, _key: str, position: int) -> None:
            self.positions.append(position)

        def read(self) -> tuple[bool, object]:
            return True, object()

        def release(self) -> None:
            self.released = True

    capture = Capture()
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(
            VideoCapture=lambda _source: capture,
            CAP_PROP_FRAME_COUNT="count",
            CAP_PROP_FPS="fps",
            CAP_PROP_POS_FRAMES="position",
            IMWRITE_JPEG_QUALITY=1,
            imencode=lambda *_args: (True, SimpleNamespace(tobytes=lambda: b"frame")),
        ),
    )
    frames = VideoProcessor().extract_keyframes(
        "offline.mp4", max_frames=10, fps_sample_rate=0.5
    )
    assert capture.positions == [0, 20, 40, 60, 80]
    assert len(frames) == len(capture.positions)
    assert capture.released


@pytest.mark.parametrize("max_frames,rate", [(0, 1.0), (1, 0.0), (1, -1.0)])
def test_invalid_sampling_options_fail_early(max_frames: int, rate: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        VideoProcessor().extract_keyframes(
            "unused.mp4", max_frames=max_frames, fps_sample_rate=rate
        )
