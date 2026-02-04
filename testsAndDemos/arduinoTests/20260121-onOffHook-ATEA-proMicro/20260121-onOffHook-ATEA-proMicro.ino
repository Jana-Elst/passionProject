const int phonePin = A1;

// Thresholds
const int ON_HOOK_MAX = 100;   
const int OFF_HOOK_MIN = 300;
const int PULSE_THRESHOLD = 700; 

int pulseCount = 0;
bool isOffHook = false;
bool inPulse = false;
unsigned long lastPulseTime = 0;
unsigned long hangupTimer = 0; // Timer to verify a real hang-up
const int timeout = 600; 
const int hangupDelay = 500; // Must be below 100 for 500ms to count as a hang-up

void setup() {
  Serial.begin(9600);
  pinMode(phonePin, INPUT); 
  Serial.println("System Ready. Lift handset...");
}

void loop() {
  int val = analogRead(phonePin);

  // 1. Hook State Detection with Buffer
  if (val > OFF_HOOK_MIN) { 
    hangupTimer = millis(); // Reset hangup timer as long as we see voltage
    if (!isOffHook) {
      isOffHook = true;
      Serial.println("\n[OFF-HOOK] Dialing enabled.");
    }
  } 
  else if (val < ON_HOOK_MAX && isOffHook) {
    // Only trigger ON-HOOK if the voltage stays low longer than hangupDelay
    if (millis() - hangupTimer > hangupDelay) {
      isOffHook = false;
      pulseCount = 0;
      Serial.println("\n[ON-HOOK] Line closed.");
    }
  }

  // 2. Pulse Detection Logic
  if (isOffHook) {
    // Detect a Pulse (Voltage jumps to ~800)
    if (val > PULSE_THRESHOLD && !inPulse) {
      inPulse = true;
      pulseCount++;
      lastPulseTime = millis();
      Serial.print("."); 
    } 
    // Detect return to Idle (Voltage drops back down)
    else if (val < PULSE_THRESHOLD && inPulse) {
      inPulse = false;
    }

    // 3. Digit Finalizer
    if (pulseCount > 0 && (millis() - lastPulseTime > timeout)) {
      int digit = (pulseCount == 10) ? 0 : pulseCount;
      Serial.print(" -> Digit Dialed: ");
      Serial.println(digit);
      pulseCount = 0; 
    }
  }
}