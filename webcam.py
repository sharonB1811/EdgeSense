import cv2
import base64
import os
from dotenv import load_dotenv
from google.cloud import aiplatform

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
