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
from botocore.exceptions import BotoCoreError, ClientError

# ===== APP SETUP =====
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACT_FILE = os.path.join(BASE_DIR, "trusted_contact.json")

# ===== AWS SES =====
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")
ses_client = boto3.client("ses", region_name=AWS_REGION)

# ===== OPTIONAL CAMERA =====
try:
    from webcam_utils import analyze_webcam_hazards
    WEBCAM_AVAILABLE = True
except Exception as e:
    WEBCAM_AVAILABLE = False
    analyze_webcam_hazards = None
    print("Webcam not available:", e, flush=True)

# ===== THRESHOLDS =====
FLOOR_DISTANCE_THRESHOLD = 15
MAX_DISTANCE_THRESHOLD = 42

# ===== DEFAULT CONTACT =====
DEFAULT_CONTACT = {
    "name": "Not set",
    "contact": "Not set",
    "contact_type": "unknown"
}

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
    "arduino_connected": False,
    "arduino_port": None
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


# ===== CONTACT PERSISTENCE =====
def ensure_contact_file_exists():
    if not os.path.exists(CONTACT_FILE):
        with open(CONTACT_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONTACT, f, indent=2)


def load_trusted_contact():
    ensure_contact_file_exists()

    try:
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = str(data.get("name", "Not set")).strip() or "Not set"
        contact = str(data.get("contact", "Not set")).strip() or "Not set"
        contact_type = detect_contact_type(contact)

        return {
            "name": name,
            "contact": contact,
            "contact_type": contact_type if contact != "Not set" else "unknown"
        }
    except Exception as e:
        print("Could not load trusted contact:", e, flush=True)
        return DEFAULT_CONTACT.copy()


def save_trusted_contact_to_file(data):
    payload = {
        "name": str(data.get("name", "Not set")).strip() or "Not set",
        "contact": str(data.get("contact", "Not set")).strip() or "Not set",
        "contact_type": str(data.get("contact_type", "unknown")).strip() or "unknown"
    }

    with open(CONTACT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


trusted_contact = load_trusted_contact()


# ===== STATUS LOGIC =====
def determine_status(distance):
    if distance < FLOOR_DISTANCE_THRESHOLD:
        return {
            "status": "WARNING",
            "hazard_level": "medium",
            "hazard_reason": "Surface detected close in front.",
            "environment": "Surface up front",
            "mobility_message": "Caution: something is very close ahead."
        }
    elif distance > MAX_DISTANCE_THRESHOLD:
        return {
            "status": "DANGER",
            "hazard_level": "high",
            "hazard_reason": "Possible drop-off detected.",
            "environment": "Watch out for downstairs",
            "mobility_message": "Stop. A drop-off may be ahead."
        }
    else:
        return {
            "status": "SAFE",
            "hazard_level": "none",
            "hazard_reason": "All is clear.",
            "environment": "Stable walking surface",
            "mobility_message": "Path appears clear."
        }


# ===== EMAIL (AWS SES) =====
def send_email_alert(to_email, subject, body):
    sender = os.environ.get("SES_SENDER_EMAIL", "").strip()

    print("DEBUG sender =", repr(sender), flush=True)
    print("DEBUG recipient =", repr(to_email), flush=True)

    if not sender:
        raise ValueError("SES sender email not set.")

    if not is_valid_email(to_email):
        raise ValueError(f"Trusted contact must be a valid email address. Got: {to_email}")

    try:
        response = ses_client.send_email(
            Source=sender,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}}
            }
        )
        print("SES success:", response, flush=True)
        return response

    except ClientError as e:
        print("SES ClientError:", e.response, flush=True)
        error_message = e.response.get("Error", {}).get("Message", str(e))
        raise RuntimeError(f"AWS SES error: {error_message}")

    except BotoCoreError as e:
        print("SES BotoCoreError:", str(e), flush=True)
        raise RuntimeError(f"AWS SES connection error: {str(e)}")

    except Exception as e:
        print("SES unknown error:", str(e), flush=True)
        raise


# ===== ALERT MESSAGE =====
def build_alert_message(alert_type):
    return (
        f"EdgeSense {alert_type}\n"
        f"Time: {now_string()}\n"
        f"Status: {current_state['status']}\n"
        f"Hazard: {current_state['hazard_reason']}\n"
        f"Environment: {current_state['environment']}\n"
        f"Distance: {current_state['distance']} cm\n"
        f"Visibility: {current_state['visibility']}\n"
        f"Camera Status: {current_state['camera_status']}\n"
        f"Camera Analysis: {current_state['camera_hazard_result']}\n"
        f"Message: {current_state['mobility_message']}"
    )


# ===== STATE UPDATE =====
def update_data(distance, visibility=None, camera_status="Idle", source="simulation"):
    computed = determine_status(distance)

    current_state.update({
        "distance": round(float(distance), 2),
        "visibility": round(float(visibility), 2) if visibility is not None else current_state["visibility"],
        "status": computed["status"],
        "hazard_level": computed["hazard_level"],
        "hazard_reason": computed["hazard_reason"],
        "environment": computed["environment"],
        "mobility_message": computed["mobility_message"],
        "camera_status": camera_status or "Idle",
        "last_updated": now_string(),
        "data_source": source
    })

    if current_state["status"] in ["WARNING", "DANGER"]:
        log_entry = {
            "timestamp": now_string(),
            "distance": current_state["distance"],
            "visibility": current_state["visibility"],
            "status": current_state["status"],
            "hazard_level": current_state["hazard_level"],
            "hazard_reason": current_state["hazard_reason"],
            "environment": current_state["environment"],
            "camera_status": current_state["camera_status"],
            "mobility_message": current_state["mobility_message"]
        }

        if not hazard_logs or hazard_logs[0] != log_entry:
            hazard_logs.insert(0, log_entry)

        if len(hazard_logs) > 50:
            del hazard_logs[50:]


# ===== CAMERA =====
def run_camera_analysis():
    if not WEBCAM_AVAILABLE or analyze_webcam_hazards is None:
        raise RuntimeError("Camera not available")

    current_state["camera_status"] = "Capturing"

    result = analyze_webcam_hazards()

    current_state["camera_hazard_result"] = result
    current_state["camera_last_capture"] = now_string()
    current_state["camera_status"] = "Complete"
    current_state["last_updated"] = now_string()

    return result


# ===== ARDUINO =====
def find_arduino_port():
    """
    Keeps COM5 as the main target since that's your USB Serial Device.
    Skips bluetooth COM ports.
    """
    ports = list_ports.comports()

    for p in ports:
        device = (p.device or "").upper()
        desc = (p.description or "").lower()

        if "bluetooth" in desc:
            continue

        if device == "COM5":
            return "COM5"

        if "arduino" in desc or "usb" in desc or "ch340" in desc or "cp210" in desc:
            return p.device

    return "COM5"

'''
def parse_arduino_line(line):
    """
    Expected format:
    DIST:12,VIS:300,CAM:Idle
    """
    parts = {}

    for item in line.split(","):
        if ":" in item:
            key, value = item.split(":", 1)
            parts[key.strip().upper()] = value.strip()

    if "DIST" not in parts:
        return None

    distance = float(parts.get("DIST", current_state["distance"]))
    visibility = float(parts.get("VIS", current_state["visibility"]))
    camera_status = parts.get("CAM", current_state["camera_status"])

    return distance, visibility, camera_status
'''

def parse_arduino_line(line):
    """
    Supports:
    1) DIST:12,VIS:300,CAM:Idle
    2) distance: 64.57 cm
    3) warning text like WATCH OUT FOR DOWNSTAIRS
    """
    cleaned = str(line).strip()
    lowered = cleaned.lower()

    # Structured format: DIST:12,VIS:300,CAM:Idle
    if "dist:" in lowered:
        parts = {}
        for item in cleaned.split(","):
            if ":" in item:
                key, value = item.split(":", 1)
                parts[key.strip().upper()] = value.strip()

        if "DIST" in parts:
            distance_match = re.search(r"[-+]?\d*\.?\d+", parts["DIST"])
            if not distance_match:
                return None

            distance = float(distance_match.group())

            vis_raw = parts.get("VIS", str(current_state["visibility"]))
            vis_match = re.search(r"[-+]?\d*\.?\d+", vis_raw)
            visibility = float(vis_match.group()) if vis_match else current_state["visibility"]

            camera_status = parts.get("CAM", current_state["camera_status"])
            return distance, visibility, camera_status

    # Plain distance line like "distance: 112.22 cm"
    if "distance" in lowered:
        match = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if match:
            distance = float(match.group())
            visibility = current_state["visibility"]
            camera_status = current_state["camera_status"]
            return distance, visibility, camera_status

    # Warning-only text
    if "watch out" in lowered or "downstairs" in lowered:
        current_state["camera_status"] = "Monitoring"
        current_state["camera_hazard_result"] = cleaned
        current_state["last_updated"] = now_string()
        return None

    return None


def read_arduino_loop():
    while True:
        port = "COM5"
        ser = None

        try:
            print(f"Trying Arduino on {port}...", flush=True)
            ser = serial.Serial(port, 9600, timeout=1)
            print(f"Opened serial on {port}", flush=True)

            time.sleep(2)
            current_state["arduino_connected"] = True
            current_state["arduino_port"] = port

            print("Waiting for Arduino data...", flush=True)

            while True:
                line = ser.readline().decode(errors="ignore").strip()

                if line:
                    print(f"RAW: {line}", flush=True)

                if not line:
                    continue

                parsed = parse_arduino_line(line)
                if parsed is None:
                    continue

                dist, vis, cam = parsed
                update_data(dist, vis, cam, source="arduino")
                print(f"Updated state from Arduino: DIST={dist}, VIS={vis}, CAM={cam}", flush=True)

        except Exception as e:
            current_state["arduino_connected"] = False
            current_state["arduino_port"] = None
            print(f"Arduino connection error: {e}", flush=True)
            time.sleep(2)

        finally:
            try:
                if ser is not None:
                    ser.close()
                    print("Serial port closed", flush=True)
            except Exception:
                pass


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
    global trusted_contact
    trusted_contact = load_trusted_contact()
    return jsonify({"success": True, "contact": trusted_contact})


@app.route("/api/contact", methods=["POST"])
def save_contact():
    global trusted_contact

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    contact = str(data.get("contact", "")).strip()

    if not name or not contact:
        return jsonify({
            "success": False,
            "message": "Please enter both a contact name and a trusted contact email."
        }), 400

    if not is_valid_email(contact):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    trusted_contact = {
        "name": name,
        "contact": contact,
        "contact_type": "email"
    }

    save_trusted_contact_to_file(trusted_contact)
    trusted_contact = load_trusted_contact()

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


@app.route("/api/analyze-camera", methods=["POST"])
def analyze_camera():
    try:
        result = run_camera_analysis()
        return jsonify({
            "success": True,
            "camera_hazard_result": result,
            "camera_last_capture": current_state["camera_last_capture"],
            "camera_status": current_state["camera_status"]
        })
    except Exception as e:
        current_state["camera_status"] = "Error"
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/checkin", methods=["POST"])
def send_checkin():
    global trusted_contact
    trusted_contact = load_trusted_contact()

    if trusted_contact["contact_type"] != "email":
        return jsonify({
            "success": False,
            "message": "Please save a trusted contact email first."
        }), 400

    message = build_alert_message("Check-In")

    log_entry = {
        "timestamp": now_string(),
        "type": "Check-In",
        "message": message,
        "contact_name": trusted_contact["name"],
        "contact": trusted_contact["contact"],
        "transport": "dashboard preview"
    }
    alert_logs.insert(0, log_entry)

    return jsonify({
        "success": True,
        "timestamp": now_string(),
        "message": "Check-in recorded successfully.",
        "contact": trusted_contact
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    global trusted_contact
    trusted_contact = load_trusted_contact()

    if trusted_contact["contact_type"] != "email":
        return jsonify({
            "success": False,
            "message": "Please save a valid trusted contact email first."
        }), 400

    subject = "EdgeSense Alert"
    message = build_alert_message("Emergency Alert")

    try:
        send_email_alert(trusted_contact["contact"], subject, message)

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
            "transport": "email",
            "subject": subject
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ===== START =====
if __name__ == "__main__":
    ensure_contact_file_exists()
    threading.Thread(target=read_arduino_loop, daemon=True).start()
    app.run(debug=True, host="127.0.0.1", port=8000, use_reloader=False)