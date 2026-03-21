
// constants won't change
const int TRIG_PIN = 6; // Arduino pin connected to Ultrasonic Sensor's TRIG pin
const int ECHO_PIN = 7; // Arduino pin connected to Ultrasonic Sensor's ECHO pin
const int LED_PIN  = 3; // Arduino pin connected to LED's pin
const int FLOOR_DISTANCE_THRESHOLD = 10; // centimeters
const int MAX_DISTANCE_THRESHOLD = 30.5;

// variables will change:
float duration_us, distance_cm;

void setup() {
  Serial.begin (9600);       // initialize serial port
  pinMode(TRIG_PIN, OUTPUT); // set arduino pin to output mode
  pinMode(ECHO_PIN, INPUT);  // set arduino pin to input mode
  pinMode(LED_PIN, OUTPUT);  // set arduino pin to output mode
}

void loop() {
  // generate 10-microsecond pulse to TRIG pin
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  // measure duration of pulse from ECHO pin
  duration_us = pulseIn(ECHO_PIN, HIGH);
  // calculate the distance
  distance_cm = 0.017 * duration_us;

  if(distance_cm < FLOOR_DISTANCE_THRESHOLD){
    digitalWrite(LED_PIN, HIGH); // turn on LED
    delay(2000);
    Serial.println("SURFACE UP FRONT");
    Serial.print("distance: ");
    Serial.print(distance_cm);
    Serial.println(" cm");
    digitalWrite(LED_PIN, LOW);
  }
  else if (distance_cm > MAX_DISTANCE_THRESHOLD){
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    Serial.println("WATCH OUT FOR DOWNSTAIRS");
    Serial.print("distance: ");
    Serial.print(distance_cm);
    Serial.println(" cm");
    digitalWrite(LED_PIN, LOW);
  }
  else {
    digitalWrite(LED_PIN, LOW);  // turn off LED
    Serial.print("distance: ");
    Serial.print(distance_cm);
    Serial.println(" cm");
  }
  delay(500);
}
