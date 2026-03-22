
// constants won't change
const int TRIG_PIN = 6; // Arduino pin connected to Ultrasonic Sensor's TRIG pin
const int ECHO_PIN = 7; // Arduino pin connected to Ultrasonic Sensor's ECHO pin
const int LED_PIN  = 3; // Arduino pin connected to LED's pin
const int BUTTON_PIN = 2;
const int FLOOR_DISTANCE_THRESHOLD = 15; // centimeters
const int MAX_DISTANCE_THRESHOLD = 42;

// variables will change:
float duration_us, distance_cm;
bool lastState = HIGH; 

void setup() {
  Serial.begin (9600);       // initialize serial port
  pinMode(TRIG_PIN, OUTPUT); // set arduino pin to output mode
  pinMode(ECHO_PIN, INPUT);  // set arduino pin to input mode
  pinMode(LED_PIN, OUTPUT);  // set arduino pin to output mode
  pinMode(BUTTON_PIN, INPUT_PULLUP);
}

void loop() {
  bool currState = digitalRead(BUTTON_PIN);
  if (lastState == HIGH && currState == LOW){
    Serial.println("CAPTURE");
    delay(200);
  }
  lastState = currState;
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
    digitalWrite(LED_PIN, LOW); // turn off LED
    Serial.println("ALL IS CLEAR");  // turn off LED
    Serial.print("distance: ");
    Serial.print(distance_cm);
    Serial.println(" cm");
  }
  delay(3000);
}
