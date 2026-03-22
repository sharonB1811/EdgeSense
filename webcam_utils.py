from google import genai
from google.genai import types
from dotenv import load_dotenv
import cv2
import os

load_dotenv()

client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT")
)

def analyze_webcam_hazards(camera_index=1):
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Failed to capture image")

    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        raise RuntimeError("Failed to encode image")

    image_bytes = buffer.tobytes()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            ),
            """
You are analyzing an image from a shoe-mounted camera.
Identify hazards that could cause a person walking forward to trip or fall within the next 3-4 steps.

Possible hazards include:
- staircases or steps (up or down)
- curbs
- drop-offs or ledges
- sudden changes in floor level
- people directly in the walking path

If a hazard is present, respond exactly in this format:
HAZARD DETECTED: <comma-separated hazards>

If no hazards are present, respond exactly:
NO HAZARD

Only output one of these responses. Do not add explanations or extra text.
            """
        ]
    )

    return response.text.strip()