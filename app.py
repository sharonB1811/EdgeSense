from flask import Flask, render_template, request, jsonify
from datetime import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import json
import os
import re

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

CONTACT_FILE = "trusted_contact.json"

current_state = {
    "distance": 12,
    "visibility": 300,
    "status": "SAFE",
    "environment": "Normal indoor/outdoor movement",
    "camera_status": "Idle",
    "last_updated": None
}

hazard_logs = []
alert_logs = []


def load_trusted_contact():
    if os.path.exists(CONTACT_FILE):
        try:
            with open(CONTACT_FILE, "r") as f:
                data = json.load(f)
                return {
                    "name": data.get("name", "Not set"),
                    "contact": data.get("contact", "Not set")
                }
        except Exception:
            pass
    return {
        "name": "Not set",
        "contact": "Not set"
    }


def save_trusted_contact_to_file(contact_data):
    with open(CONTACT_FILE, "w") as f:
        json.dump(contact_data, f)


trusted_contact = load_trusted_contact()


def determine_status(distance, visibility):
    if distance >= 20:
        return "DANGER", "Drop-off or elevation change detected"
    elif visibility >= 600:
        return "WARNING", "Low-visibility caution"
    else:
        return "SAFE", "Normal indoor/outdoor movement"


def add_hazard_log(distance, visibility, status, environment):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hazard_logs.insert(0, {
        "timestamp": timestamp,
        "distance": distance,
        "visibility": visibility,
        "status": status,
        "environment": environment
    })


def add_alert_log(alert_type, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_logs.insert(0, {
        "timestamp": timestamp,
        "type": alert_type,
        "message": message,
        "contact_name": trusted_contact["name"],
        "contact": trusted_contact["contact"]
    })


def normalize_phone_number(value):
    value = str(value).strip()
    value = re.sub(r"[^\d+]", "", value)

    if value.startswith("00"):
        value = "+" + value[2:]

    if not value.startswith("+"):
        digits_only = re.sub(r"\D", "", value)
        if len(digits_only) == 10:
            value = "+1" + digits_only
        elif len(digits_only) == 11 and digits_only.startswith("1"):
            value = "+" + digits_only

    return value


def is_valid_e164(value):
    return bool(re.fullmatch(r"\+[1-9]\d{7,14}", value))


@app.route("/")
def home():
    return render_template("index.html", page_title="Home")


@app.route("/about")
def about():
    return render_template("about.html", page_title="About")


@app.route("/features")
def features():
    return render_template("features.html", page_title="Features")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")


@app.route("/alerts")
def alerts():
    return render_template("alerts.html", page_title="Safety Alerts")


@app.route("/contact")
def contact():
    return render_template("contact.html", page_title="Contact")


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({"success": True, "data": current_state})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify({"success": True, "logs": hazard_logs})


@app.route("/api/alert-logs", methods=["GET"])
def get_alert_logs():
    return jsonify({"success": True, "logs": alert_logs})


@app.route("/api/contact", methods=["GET"])
def get_contact():
    return jsonify({"success": True, "contact": trusted_contact})


@app.route("/api/contact", methods=["POST"])
def save_contact():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    raw_contact = str(data.get("contact", "")).strip()

    if not name or not raw_contact:
        return jsonify({
            "success": False,
            "message": "Both name and phone number are required."
        }), 400

    normalized_contact = normalize_phone_number(raw_contact)

    if not is_valid_e164(normalized_contact):
        return jsonify({
            "success": False,
            "message": "Enter a valid phone number in format like +15713038776."
        }), 400

    trusted_contact["name"] = name
    trusted_contact["contact"] = normalized_contact
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
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid sensor values."
        }), 400

    camera_status = str(data.get("camera_status", current_state["camera_status"])).strip()

    status, environment = determine_status(distance, visibility)

    current_state["distance"] = distance
    current_state["visibility"] = visibility
    current_state["status"] = status
    current_state["environment"] = environment
    current_state["camera_status"] = camera_status
    current_state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if status in ["WARNING", "DANGER"]:
        add_hazard_log(distance, visibility, status, environment)

    return jsonify({
        "success": True,
        "message": "Sensor data updated successfully.",
        "data": current_state
    })


@app.route("/api/simulate", methods=["POST"])
def simulate_state():
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "safe")).lower()

    if mode == "safe":
        distance = 12
        visibility = 250
        camera_status = "Idle"
    elif mode == "warning":
        distance = 12
        visibility = 750
        camera_status = "Monitoring"
    elif mode == "danger":
        distance = 28
        visibility = 780
        camera_status = "Snapshot captured"
    else:
        return jsonify({
            "success": False,
            "message": "Invalid simulation mode."
        }), 400

    status, environment = determine_status(distance, visibility)

    current_state["distance"] = distance
    current_state["visibility"] = visibility
    current_state["status"] = status
    current_state["environment"] = environment
    current_state["camera_status"] = camera_status
    current_state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if status in ["WARNING", "DANGER"]:
        add_hazard_log(distance, visibility, status, environment)

    return jsonify({
        "success": True,
        "message": f"Simulated {mode} state.",
        "data": current_state
    })


@app.route("/api/checkin", methods=["POST"])
def checkin():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_alert_log("Check-In", f"Accessibility check-in sent at {timestamp}.")
    return jsonify({
        "success": True,
        "message": "Check-in sent successfully.",
        "timestamp": timestamp
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alert_message = (
        f"EdgeSense Help Alert\n"
        f"Time: {timestamp}\n"
        f"Status: {current_state['status']}\n"
        f"Environment: {current_state['environment']}\n"
        f"Distance: {current_state['distance']} cm\n"
        f"Visibility: {current_state['visibility']}\n"
        f"Camera: {current_state['camera_status']}"
    )

    contact_number = str(trusted_contact.get("contact", "")).strip()

    if not contact_number or contact_number == "Not set":
        return jsonify({
            "success": False,
            "message": "No trusted contact saved."
        }), 400

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        return jsonify({
            "success": False,
            "message": "Twilio environment variables are missing."
        }), 500

    if contact_number == TWILIO_FROM_NUMBER:
        return jsonify({
            "success": False,
            "message": "Trusted contact cannot be the same as the Twilio sender number."
        }), 400

    add_alert_log("Help Alert", alert_message)

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=alert_message,
            from_=TWILIO_FROM_NUMBER,
            to=contact_number
        )

        print("TWILIO SID:", message.sid)
        print("TWILIO STATUS:", message.status)
        print("TWILIO FROM:", TWILIO_FROM_NUMBER)
        print("TWILIO TO:", contact_number)

        return jsonify({
            "success": True,
            "message": "SMS request accepted by Twilio.",
            "timestamp": timestamp,
            "alert_message": alert_message,
            "contact": trusted_contact,
            "message_sid": message.sid,
            "twilio_status": message.status,
            "error_code": getattr(message, "error_code", None),
            "error_message": getattr(message, "error_message", None)
        })

    except TwilioRestException as e:
        print("TWILIO ERROR CODE:", e.code)
        print("TWILIO ERROR MESSAGE:", e.msg)
        return jsonify({
            "success": False,
            "message": f"Twilio error {e.code}: {e.msg}",
            "error_code": e.code
        }), 500

    except Exception as e:
        print("TWILIO ERROR:", str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)