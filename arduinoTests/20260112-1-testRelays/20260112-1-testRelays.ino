// Define the pin connected to the WPM406 signal (S) pin
// Based on your board file, this is Digital Pin 3
const int RELAY_PIN1 = 10;

void setup() {
  // Set the relay pin as an OUTPUT
  pinMode(RELAY_PIN1, OUTPUT);
  
  // Start with the relay OFF (NC connected to C)
  digitalWrite(RELAY_PIN1, HIGH);
  
  // Optional: Start Serial for debugging
  Serial.begin(9600);
  Serial.println("Relay Test Starting...");
}

void loop() {
  // Turn the relay ON (Energized)
  // C (Common) connects to NO (Normally Open)
  Serial.println("Relay ON (NO Active)");
}