import asyncio
import base64
import io
import cv2
import mss
import numpy as np
from PIL import Image
from backend.config import get_settings

settings = get_settings()


async def capture_screen_b64(monitor: int = 1, max_size: tuple = (1280, 720)) -> str:
    def _capture():
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[monitor])
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil.thumbnail(max_size)
            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=70)
            return base64.b64encode(buf.getvalue()).decode()
    return await asyncio.to_thread(_capture)


async def capture_camera_b64(device: int = 0) -> str | None:
    def _capture():
        cap = cv2.VideoCapture(device)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buf.tobytes()).decode()
    return await asyncio.to_thread(_capture)


def build_vision_message(b64_image: str, question: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_image}},
            {"type": "text", "text": question},
        ],
    }
