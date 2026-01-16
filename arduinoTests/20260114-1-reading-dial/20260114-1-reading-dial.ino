// const int dialPin = 6; // Connect 'b' wire here
// int pulseCount = 0;
// int lastState = LOW;
// unsigned long lastPulseTime = 0;
// const int timeout = 200; // Milliseconds to wait before deciding dialing is over

// void setup() {
//   pinMode(dialPin, INPUT_PULLUP); // Uses Arduino internal resistor
//   Serial.begin(9600);
// }

// void loop() {
//   int currentState = digitalRead(dialPin);

//   // Detect a pulse (transition from closed to open)
//   if (currentState != lastState) {
//     if (currentState == HIGH) { // The dial "broke" the connection
//       pulseCount++;
//       lastPulseTime = millis();
//     }
//     lastState = currentState;
//     delay(10); // Simple debounce
//   }

//   // If no pulses for 200ms and we have counted pulses, the digit is finished
//   if (pulseCount > 0 && (millis() - lastPulseTime) > timeout) {
//     int finalDigit = (pulseCount == 10) ? 0 : pulseCount; // 10 pulses is digit 0
//     Serial.print("Digit dialed: ");
//     Serial.println(finalDigit);
//     pulseCount = 0; // Reset for next digit
//   }
// }

//---------------------------------------------------------------------------------------------//
const int dialPin = 6; 
int pulseCount = 0;
int lastState = LOW;
unsigned long lastPulseTime = 0;
unsigned long lastDebounceTime = 0;
const int debounceDelay = 15; // Ignore pulses shorter than 15ms
const int timeout = 300;      // Wait 300ms to finish a digit

void setup() {
  pinMode(dialPin, INPUT_PULLUP);
  Serial.begin(9600);
}

void loop() {
  int reading = digitalRead(dialPin);

  // Check if the signal changed
  if (reading != lastState) {
    lastDebounceTime = millis();
  }

  // Only if the signal has been stable for longer than the debounceDelay
  if ((millis() - lastDebounceTime) > debounceDelay) {
    // If the pulse is real and the state has actually changed
    static int stableState = LOW;
    if (reading != stableState) {
      stableState = reading;
      if (stableState == HIGH) { // Pulse detected
        pulseCount++;
        lastPulseTime = millis();
      }
    }
  }

  lastState = reading;

  // Finalize the digit
  if (pulseCount > 0 && (millis() - lastPulseTime) > timeout) {
    int finalDigit = (pulseCount == 10) ? 0 : pulseCount;
    Serial.print("Digit dialed: ");
    Serial.println(finalDigit);
    pulseCount = 0;
  }
}
//---------------------------------------------------------------------------------------------//
