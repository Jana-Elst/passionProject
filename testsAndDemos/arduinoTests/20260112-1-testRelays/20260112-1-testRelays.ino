// Define the pin connected to the WPM406 signal (S) pin
// Based on your board file, this is Digital Pin 3
const int RELAY_PIN1 = 10;
const int R2 = 9;
const int R3 = 8;

const int measurePinT1 = A1;
const int measurePinT2 = A2;


void setup() {
  // Set the relay pin as an OUTPUT
  pinMode(RELAY_PIN1, OUTPUT);
  pinMode(R2, OUTPUT);
  pinMode(R3, OUTPUT);

  
  // Start with the relay OFF (NC connected to C)
  digitalWrite(RELAY_PIN1, LOW);
  digitalWrite(R2, HIGH);
  digitalWrite(R3, HIGH);

  
  // Optional: Start Serial for debugging
  Serial.begin(9600);
  Serial.println("Relay Test Starting...");
}

void loop() {
  int valueT1 = analogRead(measurePinT1);
  int valueT2 = analogRead(measurePinT2);

  Serial.print(valueT1);
  Serial.print(" | ");
  Serial.println(valueT2);
}