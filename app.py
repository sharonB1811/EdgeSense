from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import os
import re
import smtplib
import threading
import time
from email.message import EmailMessage

import serial
from serial.tools import list_ports

app = Flask(__name__)

# ===== FILE SETUP =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACT_FILE = os.path.join(BASE_DIR, "trusted_contact.json")

ALERT_EMAIL_ADDRESS = os.environ.get("ALERT_EMAIL_ADDRESS")
ALERT_EMAIL_APP_PASSWORD = os.environ.get("ALERT_EMAIL_APP_PASSWORD")

# ===== MATCH ORIGINAL ARDUINO THRESHOLDS =====
FLOOR_DISTANCE_THRESHOLD = 15
MAX_DISTANCE_THRESHOLD = 42

# ===== GLOBAL STATE =====
current_state = {
    "distance": 12.0,
    "visibility": 300.0,
    "status": "WARNING",
    "hazard_level": "medium",
    "hazard_reason": "Surface or obstacle detected close in front.",
    "environment": "Surface up front",
    "camera_status": "Idle",
    "mobility_message": "Caution: something is very close ahead.",
    "last_updated": None,
    "data_source": "simulation",
    "arduino_connected": False
}

hazard_logs = []
alert_logs = []


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ===== CONTACT HELPERS =====
def is_valid_email(value):
    value = str(value).strip()
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def is_valid_phone(value):
    value = str(value).strip()
    return bool(re.fullmatch(r"^\+?[1-9]\d{9,14}$", value))


def detect_contact_type(value):
    value = str(value).strip()
    if is_valid_email(value):
        return "email"
    if is_valid_phone(value):
        return "phone"
    return "unknown"


def load_trusted_contact():
    if os.path.exists(CONTACT_FILE):
        try:
            with open(CONTACT_FILE, "r") as f:
                data = json.load(f)
                contact_value = str(data.get("contact", "Not set")).strip()
                return {
                    "name": str(data.get("name", "Not set")).strip() or "Not set",
                    "contact": contact_value or "Not set",
                    "contact_type": detect_contact_type(contact_value)
                }
        except Exception:
            pass

    return {
        "name": "Not set",
        "contact": "Not set",
        "contact_type": "unknown"
    }


def save_trusted_contact_to_file(contact_data):
    with open(CONTACT_FILE, "w") as f:
        json.dump(contact_data, f, indent=2)


trusted_contact = load_trusted_contact()


# ===== STATUS LOGIC =====
def determine_status(distance, visibility):
    """
    Mirrors the original Arduino logic exactly:

    - distance < 15  -> SURFACE UP FRONT
    - distance > 42  -> WATCH OUT FOR DOWNSTAIRS
    - otherwise      -> ALL IS CLEAR
    """

    if distance < FLOOR_DISTANCE_THRESHOLD:
        return {
            "status": "WARNING",
            "hazard_level": "medium",
            "hazard_reason": "Surface or obstacle detected close in front.",
            "environment": "Surface up front",
            "camera_status": "Monitoring",
            "mobility_message": "Caution: something is very close ahead."
        }

    elif distance > MAX_DISTANCE_THRESHOLD:
        return {
            "status": "DANGER",
            "hazard_level": "high",
            "hazard_reason": "Possible downstairs or drop-off detected.",
            "environment": "Watch out for downstairs",
            "camera_status": "Monitoring",
            "mobility_message": "Stop and check footing. A drop-off may be ahead."
        }

    else:
        return {
            "status": "SAFE",
            "hazard_level": "none",
            "hazard_reason": "All is clear.",
            "environment": "Stable walking surface",
            "camera_status": "Idle",
            "mobility_message": "Path appears clear."
        }


# ===== LOG HELPERS =====
def add_hazard_log(state):
    entry = {
        "timestamp": now_string(),
        "distance": state["distance"],
        "visibility": state["visibility"],
        "status": state["status"],
        "hazard_level": state["hazard_level"],
        "hazard_reason": state["hazard_reason"],
        "environment": state["environment"],
        "camera_status": state["camera_status"],
        "mobility_message": state["mobility_message"]
    }

    if not hazard_logs or hazard_logs[0] != entry:
        hazard_logs.insert(0, entry)

    if len(hazard_logs) > 50:
        del hazard_logs[50:]


def add_alert_log(alert_type, message, transport="dashboard preview"):
    entry = {
        "timestamp": now_string(),
        "type": alert_type,
        "message": message,
        "transport": transport,
        "contact_name": trusted_contact["name"],
        "contact": trusted_contact["contact"],
        "contact_type": trusted_contact["contact_type"]
    }
    alert_logs.insert(0, entry)

    if len(alert_logs) > 50:
        del alert_logs[50:]


# ===== EMAIL =====
def send_email_alert(to_email, subject, body):
    if not ALERT_EMAIL_ADDRESS or not ALERT_EMAIL_APP_PASSWORD:
        raise ValueError("Email environment variables are missing.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = ALERT_EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(ALERT_EMAIL_ADDRESS, ALERT_EMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def build_alert_message(alert_type):
    return (
        f"EdgeSense {alert_type}\n"
        f"Time: {now_string()}\n"
        f"Mobility Status: {current_state['status']}\n"
        f"Hazard: {current_state['hazard_reason']}\n"
        f"Environment: {current_state['environment']}\n"
        f"Ground Distance: {current_state['distance']} cm\n"
        f"Visibility Context: {current_state['visibility']}\n"
        f"Camera: {current_state['camera_status']}\n"
        f"Message: {current_state['mobility_message']}"
    )


# ===== STATE UPDATE =====
def update_data(distance, visibility, camera_status, source="simulation"):
    computed = determine_status(distance, visibility)

    # Preserve explicit capture state from button press if present
    cleaned_camera_status = str(camera_status).strip() if camera_status is not None else ""
    if not cleaned_camera_status:
        cleaned_camera_status = computed["camera_status"]

    current_state["distance"] = round(float(distance), 2)
    current_state["visibility"] = round(float(visibility), 2)
    current_state["status"] = computed["status"]
    current_state["hazard_level"] = computed["hazard_level"]
    current_state["hazard_reason"] = computed["hazard_reason"]
    current_state["environment"] = computed["environment"]
    current_state["camera_status"] = cleaned_camera_status
    current_state["mobility_message"] = computed["mobility_message"]
    current_state["last_updated"] = now_string()
    current_state["data_source"] = source

    if current_state["status"] in ["WARNING", "DANGER"]:
        add_hazard_log(current_state)


# ===== ARDUINO SERIAL =====
def find_arduino_port():
    ports = list(list_ports.comports())

    preferred_keywords = [
        "usbmodem",
        "usbserial",
        "arduino",
        "wch",
        "cp210",
        "ch340",
        "uno r4"
    ]

    for port in ports:
        device_lower = (port.device or "").lower()
        desc_lower = (port.description or "").lower()
        hwid_lower = (port.hwid or "").lower()
        combined = f"{device_lower} {desc_lower} {hwid_lower}"

        if any(keyword in combined for keyword in preferred_keywords):
            return port.device

    return None


def parse_arduino_line(line):
    """
    Expected Arduino format:
    DIST:12.34,VIS:300,CAM:Idle
    """
    parts = {}
    for item in line.split(","):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        parts[key.strip().upper()] = value.strip()

    distance = float(parts.get("DIST", current_state["distance"]))
    visibility = float(parts.get("VIS", current_state["visibility"]))
    camera = parts.get("CAM", "Idle")
    return distance, visibility, camera


def read_arduino_loop():
    while True:
        port = find_arduino_port()

        if not port:
            current_state["arduino_connected"] = False
            time.sleep(2)
            continue

        try:
            print(f"Attempting Arduino connection on {port}")
            ser = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)  # allow board reset

            current_state["arduino_connected"] = True
            print(f"✅ Arduino connected on {port}")

            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()

                if not raw:
                    continue

                print("Arduino:", raw)

                try:
                    distance, visibility, camera = parse_arduino_line(raw)
                    update_data(distance, visibility, camera, source="arduino")
                    current_state["arduino_connected"] = True
                except Exception as parse_error:
                    print("Parse error:", parse_error)

        except Exception as connection_error:
            current_state["arduino_connected"] = False
            print("❌ Arduino connection failed:", connection_error)
            time.sleep(2)


# ===== PAGE ROUTES =====
@app.route("/")
def home():
    return render_template("dashboard.html", page_title="Dashboard")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")


@app.route("/alerts")
def alerts():
    return render_template("alerts.html", page_title="Alerts")


@app.route("/about")
def about():
    return render_template("about.html", page_title="About")


# ===== API ROUTES =====
@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "success": True,
        "data": current_state
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify({
        "success": True,
        "logs": hazard_logs
    })


@app.route("/api/alert-logs", methods=["GET"])
def get_alert_logs():
    return jsonify({
        "success": True,
        "logs": alert_logs
    })


@app.route("/api/contact", methods=["GET"])
def get_contact():
    return jsonify({
        "success": True,
        "contact": trusted_contact
    })


@app.route("/api/contact", methods=["POST"])
def save_contact():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    raw_contact = str(data.get("contact", "")).strip()

    if not name or not raw_contact:
        return jsonify({
            "success": False,
            "message": "Both name and trusted contact info are required."
        }), 400

    contact_type = detect_contact_type(raw_contact)
    if contact_type == "unknown":
        return jsonify({
            "success": False,
            "message": "Enter a valid email address or phone number in international format."
        }), 400

    trusted_contact["name"] = name
    trusted_contact["contact"] = raw_contact
    trusted_contact["contact_type"] = contact_type
    save_trusted_contact_to_file(trusted_contact)

    return jsonify({
        "success": True,
        "message": "Trusted contact saved successfully.",
        "contact": trusted_contact
    })


@app.route("/api/update", methods=["POST"])
def update_sensor_data():
    data = request.get_json(silent=True) or {}

    try:
        distance = float(data.get("distance", current_state["distance"]))
        visibility = float(data.get("visibility", current_state["visibility"]))
        camera_status = str(data.get("camera_status", current_state["camera_status"])).strip() or "Idle"
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Distance and visibility must be numeric."
        }), 400

    update_data(distance, visibility, camera_status, source="manual")

    return jsonify({
        "success": True,
        "message": "Sensor data updated successfully.",
        "data": current_state
    })


@app.route("/api/simulate", methods=["POST"])
def simulate_state():
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "safe")).strip().lower()

    if mode == "safe":
        distance = 30
        visibility = 300
        camera_status = "Idle"
    elif mode == "warning":
        distance = 10
        visibility = 300
        camera_status = "Monitoring"
    elif mode == "night":
        distance = 30
        visibility = 820
        camera_status = "Monitoring"
    elif mode == "danger":
        distance = 55
        visibility = 300
        camera_status = "Monitoring"
    else:
        return jsonify({
            "success": False,
            "message": "Invalid simulation mode."
        }), 400

    update_data(distance, visibility, camera_status, source="simulation")

    return jsonify({
        "success": True,
        "message": f"Simulated {mode} state.",
        "data": current_state
    })


@app.route("/api/checkin", methods=["POST"])
def send_checkin():
    if trusted_contact["contact_type"] == "unknown":
        return jsonify({
            "success": False,
            "message": "Set a trusted contact before sending a check-in."
        }), 400

    message = build_alert_message("Check-In")
    add_alert_log("Check-In", message, transport="dashboard preview")

    return jsonify({
        "success": True,
        "timestamp": now_string(),
        "message": "Check-in recorded successfully.",
        "contact": trusted_contact
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    if trusted_contact["contact_type"] == "unknown":
        return jsonify({
            "success": False,
            "message": "Set a valid trusted contact first."
        }), 400

    subject = "EdgeSense Emergency Alert"
    alert_message = build_alert_message("Emergency Alert")
    transport = "dashboard preview"

    try:
        if trusted_contact["contact_type"] == "email":
            send_email_alert(trusted_contact["contact"], subject, alert_message)
            transport = "email"
        else:
            transport = "phone-ready (dashboard preview only)"

        add_alert_log("Emergency Alert", alert_message, transport=transport)

        return jsonify({
            "success": True,
            "timestamp": now_string(),
            "transport": transport,
            "subject": subject,
            "alert_message": alert_message,
            "contact": trusted_contact
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


if __name__ == "__main__":
    threading.Thread(target=read_arduino_loop, daemon=True).start()
    app.run(debug=True)