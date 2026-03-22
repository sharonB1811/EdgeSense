// ===== PIN SETUP =====
const int TRIG_PIN = 6;
const int ECHO_PIN = 7;
const int LED_PIN  = 3;
const int BUTTON_PIN = 2;

// ===== THRESHOLDS =====
const int FLOOR_DISTANCE_THRESHOLD = 15; // cm
const int MAX_DISTANCE_THRESHOLD = 42;

// ===== VARIABLES =====
float duration_us, distance_cm;
int visibility = 300;         // simulated value
String cameraStatus = "Idle";

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
}

void loop() {

  // ===== BUTTON → CAMERA TRIGGER =====
  if (digitalRead(BUTTON_PIN) == LOW) {
    cameraStatus = "Capture";
  } else {
    cameraStatus = "Idle";
  }

  // ===== ULTRASONIC SENSOR =====
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  duration_us = pulseIn(ECHO_PIN, HIGH, 30000); // timeout added

  // ===== VALIDATION (IMPORTANT) =====
  if (duration_us == 0) {
    // no signal → skip this loop
    delay(100);
    return;
  }

  distance_cm = 0.017 * duration_us;

  // ignore unrealistic readings
  if (distance_cm < 2 || distance_cm > 400) {
    delay(100);
    return;
  }

  // ===== LED LOGIC =====
  if (distance_cm < FLOOR_DISTANCE_THRESHOLD) {
    digitalWrite(LED_PIN, HIGH);  // obstacle close
  }
  else if (distance_cm > MAX_DISTANCE_THRESHOLD) {
    digitalWrite(LED_PIN, HIGH);  // drop-off
  }
  else {
    digitalWrite(LED_PIN, LOW);   // safe
  }

  // ===== STRUCTURED SERIAL OUTPUT =====
  Serial.print("DIST:");
  Serial.print(distance_cm, 2);   // 2 decimal precision
  Serial.print(",VIS:");
  Serial.print(visibility);
  Serial.print(",CAM:");
  Serial.println(cameraStatus);

  delay(200);
}