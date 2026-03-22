from google import genai
import serial
import time
import base64
import os
from dotenv import load_dotenv
from google.genai import types
import cv2
import base64

SERIAL_PORT = 'COM5' # what is this?
BAUD_RATE = 9600
CAMERA_INDEX = 1

# loading API client.
load_dotenv()
client = genai.Client(vertexai=True, project = os.getenv('GOOGLE_CLOUD_PROJECT'))


cap = cv2.VideoCapture(1)  # index 1 for Logitech

if not cap.isOpened():
    print("Error: Camera could not be opened.")
    exit()
  
# setting the camera resolution.
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


def detect():
    print("Starting image capture.")
    

    # start read process. off camera after capture.
    ret, frame = cap.read() # .read returns (indicator, frame) --> ret stores success/failure.

    if not ret:
        print("Error: Failed to capture image")
        return

    cv2.imwrite("capture.jpg", frame)

    # Encode image to base64
    _, buffer = cv2.imencode('.jpg', frame)
    img_base64 = base64.b64encode(buffer).decode("utf-8")

    print("Image captured! Sending to Gemini for analysis.")

    try:
        prompt = '''
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
        response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=[
          types.Part.from_bytes(
            data=img_base64,
            mime_type='image/jpeg',
        ),
        prompt
                ]
      )
        print("-" * 30)
        # results:
        print("Result: ", response.text)
    except Exception as e:
        print(f"Error: {e}")

try:
    # create a serial port object.
    serialVar = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to serial port {SERIAL_PORT}. Waiting for button capture.")
    while True:
        # keep listening for capture - if found, run detect function.
        if serialVar.in_waiting > 0:
            line = serialVar.readline().decode('utf-8',errors = 'ignore').strip()t
            if line=='CAPTURE':
                print("Capturing!!!")
                detect()
            elif line=='WATCH OUT FOR DOWNSTAIRS':
                print('WATCH OUT')
            elif line=='SURFACE UP FRONT':
                print("SURFACE AHEAD")
except serial.SerialException as se:
    print(f"Serial Exception: {se}")
except Exception as e:
    print(f"Error: {e}")
finally:
    print("Capturing finished!")
    cap.release()
    serialVar.close()

        


