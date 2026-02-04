const int TONE_PIN1 = 19;

void setup() {  
  // Initialize Tone Pins
  pinMode(TONE_PIN1, OUTPUT);

  // Start Serial for debugging
  Serial.begin(9600);
}

void loop() {
  // --- Tone Logic ---
  // Generate tone on Pin 9 and Pin 10 at 425Hz
  tone(TONE_PIN1, 425);
  delay(1000);
}