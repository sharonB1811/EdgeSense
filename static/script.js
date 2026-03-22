async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        const result = await response.json();

        if (!result.success || !result.data) return;
        const data = result.data;

        const statusBox = document.getElementById("statusBox");
        const statusLabel = document.getElementById("statusLabel");
        const distanceValue = document.getElementById("distanceValue");
        const visibilityValue = document.getElementById("visibilityValue");
        const cameraStatus = document.getElementById("cameraStatus");
        const lastUpdated = document.getElementById("lastUpdated");
        const dashboardStatusTitle = document.getElementById("dashboardStatusTitle");
        const dashboardEnvironment = document.getElementById("dashboardEnvironment");
        const hazardReason = document.getElementById("hazardReason");
        const mobilityMessage = document.getElementById("mobilityMessage");

        if (statusBox) {
            statusBox.className = "status-box";
            if (data.status) {
                statusBox.classList.add(data.status.toLowerCase());
            }
        }

        if (statusLabel) statusLabel.textContent = data.status || "SAFE";
        if (distanceValue) distanceValue.textContent = `${data.distance ?? "--"} cm`;
        if (visibilityValue) visibilityValue.textContent = `${data.visibility ?? "--"}`;
        if (cameraStatus) cameraStatus.textContent = data.camera_status || "Idle";
        if (lastUpdated) lastUpdated.textContent = data.last_updated || "Not yet updated";
        if (dashboardStatusTitle) dashboardStatusTitle.textContent = data.status || "SAFE";
        if (dashboardEnvironment) dashboardEnvironment.textContent = data.environment || "Stable walking surface";
        if (hazardReason) hazardReason.textContent = data.hazard_reason || "No immediate hazard detected.";
        if (mobilityMessage) mobilityMessage.textContent = data.mobility_message || "Path appears stable.";
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

        const logs = result.logs || [];

        if (logs.length === 0) {
            logContainer.innerHTML = `<p class="empty-log">No mobility hazard events recorded yet.</p>`;
            return;
        }

        logContainer.innerHTML = logs.map(log => `
            <div class="log-item">
                <strong>${log.status} · ${log.environment}</strong>
                <p><span class="log-label">Hazard:</span> ${log.hazard_reason}</p>
                <p><span class="log-label">Ground Distance:</span> ${log.distance} cm</p>
                <p><span class="log-label">Visibility Context:</span> ${log.visibility}</p>
                <p><span class="log-label">Camera:</span> ${log.camera_status}</p>
                <p><span class="log-label">Mobility Guidance:</span> ${log.mobility_message}</p>
                <p><span class="log-label">Time:</span> ${log.timestamp}</p>
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

        const logs = result.logs || [];

        if (logs.length === 0) {
            alertLogContainer.innerHTML = `<p class="empty-log">No check-ins or emergency alerts yet.</p>`;
            return;
        }

        alertLogContainer.innerHTML = logs.map(log => `
            <div class="log-item">
                <strong>${log.type}</strong>
                <p><span class="log-label">Delivery:</span> ${log.transport || "dashboard preview"}</p>
                <p>${(log.message || "").replace(/\n/g, "<br>")}</p>
                <p><span class="log-label">Trusted Contact:</span> ${log.contact_name} (${log.contact})</p>
                <p><span class="log-label">Time:</span> ${log.timestamp}</p>
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

        const contact = result.contact || {};

        const savedName = document.getElementById("savedContactName");
        const savedInfo = document.getElementById("savedContactInfo");
        const savedType = document.getElementById("savedContactType");
        const nameInput = document.getElementById("contactName");
        const infoInput = document.getElementById("contactInfo");

        if (savedName) savedName.textContent = contact.name || "Not set";
        if (savedInfo) savedInfo.textContent = contact.contact || "Not set";
        if (savedType) savedType.textContent = contact.contact_type || "unknown";

        if (nameInput && contact.name && contact.name !== "Not set") {
            nameInput.value = contact.name;
        }

        if (infoInput && contact.contact && contact.contact !== "Not set") {
            infoInput.value = contact.contact;
        }
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
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: nameInput.value.trim(),
                contact: infoInput.value.trim()
            })
        });

        const result = await response.json();

        if (contactMessage) {
            contactMessage.textContent = result.message || (result.success ? "Trusted contact saved." : "Failed to save trusted contact.");
        }

        if (result.success) {
            await fetchTrustedContact();
        }
    } catch (error) {
        console.error("Error saving trusted contact:", error);
        if (contactMessage) {
            contactMessage.textContent = "Error saving trusted contact.";
        }
    }
}

async function simulateMode(mode) {
    try {
        const response = await fetch("/api/simulate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ mode })
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
            headers: {
                "Content-Type": "application/json"
            },
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
        const response = await fetch("/api/checkin", {
            method: "POST"
        });

        const result = await response.json();

        if (checkinMessage) {
            checkinMessage.textContent = result.success
                ? `Check-in recorded at ${result.timestamp}`
                : (result.message || "Check-in failed.");
        }

        await fetchAlertLogs();
    } catch (error) {
        console.error("Error sending check-in:", error);
        if (checkinMessage) {
            checkinMessage.textContent = "Error sending check-in.";
        }
    }
}

async function sendHelpAlert() {
    const alertMessage = document.getElementById("alertMessage");
    const alertPreview = document.getElementById("alertPreview");

    try {
        const response = await fetch("/api/send-alert", {
            method: "POST"
        });

        const result = await response.json();

        if (result.success) {
            if (alertMessage) {
                alertMessage.textContent = `Emergency alert recorded at ${result.timestamp}`;
            }

            if (alertPreview) {
                alertPreview.innerHTML = `
                    <strong>Alert recipient:</strong> ${result.contact.name} (${result.contact.contact})<br><br>
                    <strong>Delivery:</strong> ${result.transport}<br>
                    <strong>Subject:</strong> ${result.subject}<br><br>
                    <strong>Message:</strong><br>
                    ${result.alert_message.replace(/\n/g, "<br>")}
                `;
            }
        } else {
            if (alertMessage) {
                alertMessage.textContent = `Error: ${result.message}`;
            }

            if (alertPreview) {
                alertPreview.innerHTML = `
                    <strong>Alert failed.</strong><br><br>
                    ${result.message}
                `;
            }
        }

        await fetchAlertLogs();
    } catch (error) {
        console.error("Error sending help alert:", error);

        if (alertMessage) {
            alertMessage.textContent = "Error: Could not reach backend.";
        }

        if (alertPreview) {
            alertPreview.innerHTML = `
                <strong>Request failed.</strong><br><br>
                Check the Flask terminal and browser console for details.
            `;
        }
    }
}

function startAutoRefresh() {
    setInterval(async () => {
        await fetchStatus();
        await fetchLogs();
    }, 1000);
}

document.addEventListener("DOMContentLoaded", async () => {
    await fetchStatus();
    await fetchLogs();
    await fetchAlertLogs();
    await fetchTrustedContact();
    startAutoRefresh();
});