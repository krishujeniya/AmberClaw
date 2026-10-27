from amberclaw.multimodal.image import ImageMetadata, ImageProcessor
from amberclaw.multimodal.router import AttachmentMedia, MultimodalRouter
from amberclaw.multimodal.video import VideoProcessor


def test_image_processor_data_url():
    processor = ImageProcessor()
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"

    data_url = processor.to_base64_data_url(dummy_png)
    assert data_url.startswith("data:image/png;base64,")

    metadata = processor.get_metadata(dummy_png)
    assert isinstance(metadata, ImageMetadata)
    assert metadata.mime_type == "image/png"


def test_image_vision_content():
    processor = ImageProcessor()
    dummy_jpg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xd9"
    )

    vision_item = processor.to_vision_message_content(dummy_jpg)
    assert vision_item["type"] == "image_url"
    assert vision_item["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_video_processor_keyframes():
    processor = VideoProcessor()
    dummy_mp4 = b"ftypisom\x00\x00\x02\x00isomiso2mp41"
    keyframes = processor.extract_keyframes(dummy_mp4, max_frames=3)
    assert len(keyframes) == 3


def test_multimodal_router():
    router = MultimodalRouter()
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"

    attachment = AttachmentMedia(media_type="image", data_or_path=dummy_png)
    msg = router.create_multimodal_message(
        "What is in this image?", attachments=[attachment]
    )

    assert msg["role"] == "user"
    assert isinstance(msg["content"], list)
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][0]["text"] == "What is in this image?"
    assert msg["content"][1]["type"] == "image_url"
