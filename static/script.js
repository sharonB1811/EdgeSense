async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        const result = await response.json();
        if (!result.success) return;

        const data = result.data;

        const statusBox = document.getElementById("statusBox");
        const statusLabel = document.getElementById("statusLabel");
        const distanceValue = document.getElementById("distanceValue");
        const visibilityValue = document.getElementById("visibilityValue");
        const cameraStatus = document.getElementById("cameraStatus");
        const lastUpdated = document.getElementById("lastUpdated");
        const dashboardStatusTitle = document.getElementById("dashboardStatusTitle");
        const dashboardEnvironment = document.getElementById("dashboardEnvironment");

        if (statusBox && statusLabel) {
            statusBox.className = "status-box " + data.status.toLowerCase();
            statusLabel.textContent = data.status;
        }
        if (distanceValue) distanceValue.textContent = `${data.distance} cm`;
        if (visibilityValue) visibilityValue.textContent = `${data.visibility}`;
        if (cameraStatus) cameraStatus.textContent = data.camera_status;
        if (lastUpdated) lastUpdated.textContent = data.last_updated || "Not yet updated";
        if (dashboardStatusTitle) dashboardStatusTitle.textContent = data.status;
        if (dashboardEnvironment) dashboardEnvironment.textContent = data.environment;
    } catch (error) {
        console.error("Error fetching status:", error);
    }
}

async function fetchLogs() {
    try {
        const response = await fetch("/api/logs");
        const result = await response.json();
        if (!result.success) return;

        const logContainer = document.getElementById("logContainer");
        if (!logContainer) return;

        const logs = result.logs;
        if (logs.length === 0) {
            logContainer.innerHTML = `<p class="empty-log">No warnings or danger events yet.</p>`;
            return;
        }

        logContainer.innerHTML = logs.map(log => `
            <div class="log-item">
                <strong>${log.status} - ${log.environment}</strong>
                <p>Distance: ${log.distance} cm</p>
                <p>Visibility Risk: ${log.visibility}</p>
                <p>Time: ${log.timestamp}</p>
            </div>
        `).join("");
    } catch (error) {
        console.error("Error fetching logs:", error);
    }
}

async function fetchAlertLogs() {
    try {
        const response = await fetch("/api/alert-logs");
        const result = await response.json();
        if (!result.success) return;

        const alertLogContainer = document.getElementById("alertLogContainer");
        if (!alertLogContainer) return;

        const logs = result.logs;
        if (logs.length === 0) {
            alertLogContainer.innerHTML = `<p class="empty-log">No check-ins or help alerts yet.</p>`;
            return;
        }

        alertLogContainer.innerHTML = logs.map(log => `
            <div class="log-item">
                <strong>${log.type}</strong>
                <p>${log.message}</p>
                <p>Trusted Contact: ${log.contact_name} (${log.contact})</p>
                <p>Time: ${log.timestamp}</p>
            </div>
        `).join("");
    } catch (error) {
        console.error("Error fetching alert logs:", error);
    }
}

async function fetchTrustedContact() {
    try {
        const response = await fetch("/api/contact");
        const result = await response.json();
        if (!result.success) return;

        const contact = result.contact;

        const savedName = document.getElementById("savedContactName");
        const savedInfo = document.getElementById("savedContactInfo");
        const nameInput = document.getElementById("contactName");
        const infoInput = document.getElementById("contactInfo");

        if (savedName) savedName.textContent = contact.name;
        if (savedInfo) savedInfo.textContent = contact.contact;
        if (nameInput && contact.name !== "Not set") nameInput.value = contact.name;
        if (infoInput && contact.contact !== "Not set") infoInput.value = contact.contact;
    } catch (error) {
        console.error("Error fetching trusted contact:", error);
    }
}

async function saveTrustedContact() {
    const nameInput = document.getElementById("contactName");
    const infoInput = document.getElementById("contactInfo");
    const contactMessage = document.getElementById("contactMessage");
    if (!nameInput || !infoInput) return;

    try {
        const response = await fetch("/api/contact", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                name: nameInput.value.trim(),
                contact: infoInput.value.trim()
            })
        });

        const result = await response.json();
        if (result.success) {
            if (contactMessage) contactMessage.textContent = result.message;
            await fetchTrustedContact();
        } else if (contactMessage) {
            contactMessage.textContent = result.message || "Failed to save contact.";
        }
    } catch (error) {
        console.error("Error saving trusted contact:", error);
    }
}

async function simulateMode(mode) {
    try {
        const response = await fetch("/api/simulate", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ mode: mode })
        });

        const result = await response.json();
        if (result.success) {
            await fetchStatus();
            await fetchLogs();
        }
    } catch (error) {
        console.error("Error simulating mode:", error);
    }
}

async function sendManualUpdate() {
    const distanceInput = document.getElementById("distanceInput");
    const visibilityInput = document.getElementById("visibilityInput");
    const cameraInput = document.getElementById("cameraInput");
    if (!distanceInput || !visibilityInput || !cameraInput) return;

    try {
        const response = await fetch("/api/update", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                distance: Number(distanceInput.value),
                visibility: Number(visibilityInput.value),
                camera_status: cameraInput.value.trim()
            })
        });

        const result = await response.json();
        if (result.success) {
            await fetchStatus();
            await fetchLogs();
        }
    } catch (error) {
        console.error("Error updating sensor data:", error);
    }
}

async function sendCheckin() {
    const checkinMessage = document.getElementById("checkinMessage");

    try {
        const response = await fetch("/api/checkin", { method: "POST" });
        const result = await response.json();

        if (result.success) {
            if (checkinMessage) {
                checkinMessage.textContent = `Check-in sent at ${result.timestamp}`;
            }
            await fetchAlertLogs();
        }
    } catch (error) {
        console.error("Error sending check-in:", error);
    }
}

async function sendHelpAlert() {
    const alertMessage = document.getElementById("alertMessage");
    const alertPreview = document.getElementById("alertPreview");

    try {
        const response = await fetch("/api/send-alert", { method: "POST" });
        const result = await response.json();

        if (result.success) {
            if (alertMessage) {
                alertMessage.textContent = `Help alert sent at ${result.timestamp}`;
            }

            if (alertPreview) {
                alertPreview.innerHTML = `
                    <strong>Alert sent to:</strong> ${result.contact.name} (${result.contact.contact})<br><br>
                    <strong>Message:</strong><br>
                    ${result.alert_message}
                `;
            }

            await fetchAlertLogs();
        }
    } catch (error) {
        console.error("Error sending help alert:", error);
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    await fetchStatus();
    await fetchLogs();
    await fetchAlertLogs();
    await fetchTrustedContact();
});