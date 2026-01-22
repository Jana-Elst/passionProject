const int RELAY_PIN1 = 7;
const int RELAY_PIN2 = 8;
const int dialPin2 = 19; 
const int dialPin1 = 20; 

int pulseCount = 0;
int lastState = LOW;
unsigned long lastPulseTime = 0;
unsigned long lastDebounceTime = 0;
const int debounceDelay = 15; // Ignore pulses shorter than 15ms
const int timeout = 300;      // Wait 300ms to finish a digit


void setup() {
  // Set the relay pin as an OUTPUT
  pinMode(RELAY_PIN1, OUTPUT);
  pinMode(RELAY_PIN2, OUTPUT);
  pinMode(dialPin1, INPUT_PULLUP);
  pinMode(dialPin2, INPUT_PULLUP);

  
  digitalWrite(RELAY_PIN1, LOW);
  digitalWrite(RELAY_PIN2, LOW);

  Serial.begin(9600);
}

void loop() {
  int reading = digitalRead(dialPin1);

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
