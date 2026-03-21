from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

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

trusted_contact = {
    "name": "Not set",
    "contact": "Not set"
}


def determine_status(distance, visibility):
    """
    Accessibility-focused logic:
    - DANGER: likely drop-off / stairs / curb detected
    - WARNING: elevated visibility risk or caution condition
    - SAFE: normal walking condition
    """
    drop_threshold = 20
    visibility_warning_threshold = 600

    if distance >= drop_threshold:
        return "DANGER", "Drop-off or elevation change detected"
    elif visibility >= visibility_warning_threshold:
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
    if len(hazard_logs) > 20:
        hazard_logs.pop()


def add_alert_log(alert_type, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_logs.insert(0, {
        "timestamp": timestamp,
        "type": alert_type,
        "message": message,
        "contact_name": trusted_contact["name"],
        "contact": trusted_contact["contact"]
    })
    if len(alert_logs) > 20:
        alert_logs.pop()


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
    contact = str(data.get("contact", "")).strip()

    if not name or not contact:
        return jsonify({
            "success": False,
            "message": "Both name and contact are required."
        }), 400

    trusted_contact["name"] = name
    trusted_contact["contact"] = contact

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
    add_alert_log("Check-In", f"User accessibility safety check-in sent at {timestamp}.")
    return jsonify({
        "success": True,
        "message": "Check-in sent successfully.",
        "timestamp": timestamp
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alert_message = (
        f"Help alert triggered at {timestamp}. "
        f"Status: {current_state['status']}. "
        f"Environment: {current_state['environment']}. "
        f"Distance: {current_state['distance']} cm. "
        f"Visibility risk: {current_state['visibility']}. "
        f"Camera: {current_state['camera_status']}."
    )

    add_alert_log("Help Alert", alert_message)

    return jsonify({
        "success": True,
        "message": "Help alert sent successfully.",
        "timestamp": timestamp,
        "alert_message": alert_message,
        "contact": trusted_contact
    })


if __name__ == "__main__":
    app.run(debug=True)