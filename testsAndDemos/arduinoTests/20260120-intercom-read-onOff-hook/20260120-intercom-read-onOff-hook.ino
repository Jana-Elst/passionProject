const int phonePin = A1;

// thresholds based on your measurement
const int ON_HOOK_LIMIT = 100;   // Near 0
const int OFF_HOOK_LEVEL = 400;  // Your measured Off-Hook
const int PULSE_THRESHOLD = 500; // The "midway" point to detect a break

int pulseCount = 0;
bool isOffHook = false;
bool inPulse = false;
unsigned long lastPulseTime = 0;
const int timeout = 400; // If no pulse for 400ms, dialing is done

void setup() {
  Serial.begin(9600);
  Serial.println("Ready. Lift handset to start.");
}

void loop() {
  int val = analogRead(phonePin);

  // 1. Hook State Detection
  if (val > (OFF_HOOK_LEVEL - 100)) { 
    if (!isOffHook) {
      isOffHook = true;
      Serial.println("\n[OFF-HOOK]");
    }
  } else if (val < ON_HOOK_LIMIT) {
    if (isOffHook && pulseCount == 0) { // Only hang up if not currently dialing
      isOffHook = false;
      Serial.println("\n[ON-HOOK]");
    }
  }

  // 2. Pulse Detection (Only runs if handset is lifted)
  if (isOffHook) {
    // When dialing, the voltage drops from 780 towards 0 (the break)
    if (val < PULSE_THRESHOLD && !inPulse) {
      inPulse = true;
      pulseCount++;
      lastPulseTime = millis();
      Serial.print("."); // This is the dot you are seeing
    } 
    // Return to "Off-Hook" level ends the pulse
    else if (val > PULSE_THRESHOLD && inPulse) {
      inPulse = false;
    }
  }

  // 3. Digit Finalizer (The fix for the "only dots" problem)
  if (pulseCount > 0 && (millis() - lastPulseTime > timeout)) {
    int digit = (pulseCount == 10) ? 0 : pulseCount;
    Serial.print(" Digit: ");
    Serial.println(digit);
    
    pulseCount = 0; // Reset for next digit
  }
}