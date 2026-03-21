import cv2
import base64
import os
from dotenv import load_dotenv
from google.cloud import aiplatform

# Load .env and service account
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Initialize AI Platform
PROJECT_ID = "gemini-hazard-detection"  # replace with your Google Cloud project ID
LOCATION = "us-central1"        # or your preferred location
ENDPOINT_ID = "YOUR_GEMINI_ENDPOINT_ID"  # replace with your deployed Gemini Pro endpoint

aiplatform.init(project=PROJECT_ID, location=LOCATION)
client = aiplatform.gapic.PredictionServiceClient()
endpoint_path = client.endpoint_path(PROJECT_ID, LOCATION, ENDPOINT_ID)

# -------------------------------
# Capture image from Logitech webcam
cap = cv2.VideoCapture(1)  # index 1 for Logitech
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

ret, frame = cap.read()
cap.release()

if not ret:
    raise RuntimeError("Failed to capture image")

# Optional: save locally
cv2.imwrite("capture.jpg", frame)

# Encode image to base64
_, buffer = cv2.imencode('.jpg', frame)
img_base64 = base64.b64encode(buffer).decode("utf-8")

# -------------------------------
# Prepare instance for Gemini Pro
instance = {
    "content": "Detect hazards in this image: staircase, drop-off, curbs, or people.",
    "mime_type": "text/plain",
    "image": img_base64
}

# Send request to Gemini Pro
response = client.predict(
    endpoint=endpoint_path,
    instances=[instance]
)

# Print Gemini’s classification
print("Gemini Pro output:")
print(response.predictions)