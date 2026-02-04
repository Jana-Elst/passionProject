const int phonePin = A2;

// Thresholds based on your measurements
const int ON_HOOK_LIMIT = 100;   
const int PULSE_LOW_THRESHOLD = 300; // Anything below this is a "break" (pulse)
const int PULSE_HIGH_THRESHOLD = 450; // Anything above this is "off-hook" (idle)

int pulseCount = 0;
bool isOffHook = false;
bool inPulse = false;
unsigned long lastPulseTime = 0;
const int timeout = 600; // Increased to 600ms for older, slower dials

void setup() {
  Serial.begin(9600);
  pinMode(phonePin, INPUT); // Ensure pin is input
  Serial.println("System Ready. Lift handset...");
}

void loop() {
  int val = analogRead(phonePin);

  // 1. Hook State Detection
  if (val > PULSE_HIGH_THRESHOLD) { 
    if (!isOffHook) {
      isOffHook = true;
      Serial.println("\n[OFF-HOOK] Dialing enabled.");
    }
  } else if (val < ON_HOOK_LIMIT) {
    if (isOffHook && pulseCount == 0) {
      isOffHook = false;
      Serial.println("\n[ON-HOOK] Line closed.");
    }
  }

  // 2. Pulse Detection Logic
  if (isOffHook) {
    // Detect the START of a pulse (Voltage drops)
    if (val < PULSE_LOW_THRESHOLD && !inPulse) {
      inPulse = true;
      pulseCount++;
      lastPulseTime = millis();
      Serial.print("."); 
    } 
    // Detect the END of a pulse (Voltage returns)
    else if (val > PULSE_HIGH_THRESHOLD && inPulse) {
      inPulse = false;
    }

    // 3. Digit Finalizer
    // If we have pulses and haven't seen a new one within the timeout
    if (pulseCount > 0 && (millis() - lastPulseTime > timeout)) {
      // Rotary phones: 10 pulses = Digit 0
      int digit = (pulseCount == 10) ? 0 : pulseCount;
      
      Serial.print(" -> Digit Dialed: ");
      Serial.println(digit);
      
      pulseCount = 0; // Reset count for the next digit
    }
  }
}