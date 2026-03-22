from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import os
import re
import threading
import time
import boto3
import serial
from serial.tools import list_ports

# ===== AWS SES =====
ses_client = boto3.client("ses")

# ===== OPTIONAL CAMERA =====
try:
    from webcam_utils import analyze_webcam_hazards
    WEBCAM_AVAILABLE = True
except Exception as e:
    WEBCAM_AVAILABLE = False
    print("Webcam not available:", e)

app = Flask(__name__)

# ===== FILE SETUP =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACT_FILE = os.path.join(BASE_DIR, "trusted_contact.json")

# ===== THRESHOLDS =====
FLOOR_DISTANCE_THRESHOLD = 15
MAX_DISTANCE_THRESHOLD = 42

# ===== GLOBAL STATE =====
current_state = {
    "distance": 12.0,
    "visibility": 300.0,
    "status": "SAFE",
    "hazard_level": "none",
    "hazard_reason": "All is clear.",
    "environment": "Stable walking surface",
    "camera_status": "Idle",
    "camera_hazard_result": "No camera analysis yet.",
    "camera_last_capture": None,
    "mobility_message": "Path appears clear.",
    "last_updated": None,
    "data_source": "simulation",
    "arduino_connected": False
}

hazard_logs = []
alert_logs = []

# ===== HELPERS =====
def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_valid_email(value):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value).strip()))

def detect_contact_type(value):
    if is_valid_email(value):
        return "email"
    return "unknown"

# ===== CONTACT =====
def load_trusted_contact():
    if os.path.exists(CONTACT_FILE):
        try:
            with open(CONTACT_FILE, "r") as f:
                data = json.load(f)
                contact_value = str(data.get("contact", "Not set")).strip()
                return {
                    "name": data.get("name", "Not set"),
                    "contact": contact_value,
                    "contact_type": detect_contact_type(contact_value)
                }
        except:
            pass

    return {"name": "Not set", "contact": "Not set", "contact_type": "unknown"}

def save_trusted_contact_to_file(data):
    with open(CONTACT_FILE, "w") as f:
        json.dump(data, f, indent=2)

trusted_contact = load_trusted_contact()

# ===== STATUS LOGIC =====
def determine_status(distance):
    if distance < FLOOR_DISTANCE_THRESHOLD:
        return {
            "status": "WARNING",
            "hazard_reason": "Surface detected close in front.",
            "environment": "Surface up front",
            "mobility_message": "Caution: something is very close ahead."
        }
    elif distance > MAX_DISTANCE_THRESHOLD:
        return {
            "status": "DANGER",
            "hazard_reason": "Possible drop-off detected.",
            "environment": "Watch out for downstairs",
            "mobility_message": "Stop. A drop-off may be ahead."
        }
    else:
        return {
            "status": "SAFE",
            "hazard_reason": "All is clear.",
            "environment": "Stable walking surface",
            "mobility_message": "Path appears clear."
        }

# ===== EMAIL (AWS SES) =====
def send_email_alert(to_email, subject, body):
    sender = os.environ.get("SES_SENDER_EMAIL")

    if not sender:
        raise ValueError("SES sender email not set")

    ses_client.send_email(
        Source=sender,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )

# ===== ALERT MESSAGE =====
def build_alert_message(alert_type):
    return (
        f"EdgeSense {alert_type}\n"
        f"Time: {now_string()}\n"
        f"Status: {current_state['status']}\n"
        f"Hazard: {current_state['hazard_reason']}\n"
        f"Distance: {current_state['distance']} cm\n"
        f"Camera: {current_state['camera_hazard_result']}\n"
        f"Message: {current_state['mobility_message']}"
    )

# ===== STATE UPDATE =====
def update_data(distance, camera_status="Idle"):
    computed = determine_status(distance)

    current_state.update({
        "distance": round(distance, 2),
        "status": computed["status"],
        "hazard_reason": computed["hazard_reason"],
        "environment": computed["environment"],
        "mobility_message": computed["mobility_message"],
        "camera_status": camera_status,
        "last_updated": now_string()
    })

    if current_state["status"] in ["WARNING", "DANGER"]:
        hazard_logs.insert(0, current_state.copy())

# ===== CAMERA =====
def run_camera_analysis():
    if not WEBCAM_AVAILABLE:
        raise RuntimeError("Camera not available")

    current_state["camera_status"] = "Capturing"

    result = analyze_webcam_hazards()

    current_state["camera_hazard_result"] = result
    current_state["camera_last_capture"] = now_string()
    current_state["camera_status"] = "Complete"

# ===== ARDUINO =====
def find_arduino_port():
    ports = list_ports.comports()
    for p in ports:
        if "usb" in p.device.lower():
            return p.device
    return None

def read_arduino_loop():
    while True:
        port = find_arduino_port()

        if not port:
            current_state["arduino_connected"] = False
            time.sleep(2)
            continue

        try:
            ser = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)

            current_state["arduino_connected"] = True

            while True:
                line = ser.readline().decode().strip()

                if not line:
                    continue

                if "DIST:" in line:
                    try:
                        dist = float(line.split(",")[0].split(":")[1])
                        update_data(dist)
                    except:
                        pass

        except Exception as e:
            current_state["arduino_connected"] = False
            print("Arduino error:", e)
            time.sleep(2)

# ===== PAGE ROUTES =====
@app.route("/")
def home():
    return render_template("dashboard.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/alerts")
def alerts():
    return render_template("alerts.html")

@app.route("/about")
def about():
    return render_template("about.html")

# ===== API =====
@app.route("/api/status")
def get_status():
    return jsonify({"success": True, "data": current_state})

@app.route("/api/logs")
def get_logs():
    return jsonify({"success": True, "logs": hazard_logs})

@app.route("/api/alert-logs")
def get_alert_logs():
    return jsonify({"success": True, "logs": alert_logs})

@app.route("/api/contact", methods=["GET"])
def get_contact():
    return jsonify({"success": True, "contact": trusted_contact})

@app.route("/api/contact", methods=["POST"])
def save_contact():
    data = request.json

    trusted_contact["name"] = data["name"]
    trusted_contact["contact"] = data["contact"]
    trusted_contact["contact_type"] = detect_contact_type(data["contact"])

    save_trusted_contact_to_file(trusted_contact)

    return jsonify({"success": True, "message": "Contact saved", "contact": trusted_contact})

@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    if trusted_contact["contact_type"] != "email":
        return jsonify({"success": False, "message": "Use email contact only"})

    message = build_alert_message("Emergency Alert")

    try:
        send_email_alert(trusted_contact["contact"], "EdgeSense Alert", message)

        log_entry = {
            "timestamp": now_string(),
            "type": "Emergency Alert",
            "message": message,
            "contact_name": trusted_contact["name"],
            "contact": trusted_contact["contact"],
            "transport": "email"
        }

        alert_logs.insert(0, log_entry)

        return jsonify({
            "success": True,
            "timestamp": now_string(),
            "alert_message": message,
            "contact": trusted_contact,
            "transport": "email"
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/analyze-camera", methods=["POST"])
def analyze_camera():
    try:
        run_camera_analysis()
        return jsonify({
            "success": True,
            "camera_hazard_result": current_state["camera_hazard_result"],
            "camera_last_capture": current_state["camera_last_capture"],
            "camera_status": current_state["camera_status"]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ===== START =====
if __name__ == "__main__":
    threading.Thread(target=read_arduino_loop, daemon=True).start()
    app.run(debug=True)