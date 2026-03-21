from google import genai
import os
from dotenv import load_dotenv
from google.genai import types
import cv2
import base64

load_dotenv()

client = genai.Client(vertexai=True, project = os.getenv('GOOGLE_CLOUD_PROJECT'))


cap = cv2.VideoCapture(1)  # index 1 for Logitech
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

ret, frame = cap.read()
cap.release()

if not ret:
    raise RuntimeError("Failed to capture image")

cv2.imwrite("capture.jpg", frame)

# Encode image to base64
_, buffer = cv2.imencode('.jpg', frame)
img_base64 = base64.b64encode(buffer).decode("utf-8")

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
      types.Part.from_bytes(
        data=img_base64,
        mime_type='image/jpeg',
      ),
      '''
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
      '''
    ]
  )

print("Gemini Pro output:")
print(response.text)