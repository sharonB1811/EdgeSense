from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import os
import re
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

CONTACT_FILE = "trusted_contact.json"

ALERT_EMAIL_ADDRESS = os.environ.get("ALERT_EMAIL_ADDRESS")
ALERT_EMAIL_APP_PASSWORD = os.environ.get("ALERT_EMAIL_APP_PASSWORD")

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


def is_valid_email(value):
    value = str(value).strip()
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


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
            "message": "Both name and email are required."
        }), 400

    if not is_valid_email(raw_contact):
        return jsonify({
            "success": False,
            "message": "Enter a valid email address."
        }), 400

    trusted_contact["name"] = name
    trusted_contact["contact"] = raw_contact
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
    add_alert_log("Check-In", f"Accessibility check-in recorded at {timestamp}.")
    return jsonify({
        "success": True,
        "message": "Check-in recorded successfully.",
        "timestamp": timestamp
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    contact_email = str(trusted_contact.get("contact", "")).strip()

    if not contact_email or contact_email == "Not set":
        return jsonify({
            "success": False,
            "message": "No trusted contact email saved."
        }), 400

    if not is_valid_email(contact_email):
        return jsonify({
            "success": False,
            "message": "Saved trusted contact is not a valid email address."
        }), 400

    subject = "EdgeSense Emergency Alert"
    alert_message = (
        f"EdgeSense Emergency Alert\n\n"
        f"Time: {timestamp}\n"
        f"Trusted Contact: {trusted_contact['name']}\n"
        f"Status: {current_state['status']}\n"
        f"Environment: {current_state['environment']}\n"
        f"Distance: {current_state['distance']} cm\n"
        f"Visibility: {current_state['visibility']}\n"
        f"Camera: {current_state['camera_status']}\n"
        f"Last Updated: {current_state['last_updated'] or 'Not available'}\n\n"
        f"This alert was triggered from the EdgeSense dashboard."
    )

    add_alert_log("Help Alert", alert_message)

    try:
        send_email_alert(contact_email, subject, alert_message)

        return jsonify({
            "success": True,
            "message": "Emergency email sent successfully.",
            "timestamp": timestamp,
            "contact": trusted_contact,
            "subject": subject,
            "alert_message": alert_message,
            "transport": "email"
        })

    except Exception as e:
        print("EMAIL ERROR:", str(e))
        return jsonify({
            "success": False,
            "message": f"Email send failed: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)