//--- PINS
const int relaysPin = 10;
const int measurePinT1 = A1;
const int measurePinT2 = A2;

#define T1 0
#define T2 1

struct PhoneConfig {
  int pickupThreshold;
  int hangupThreshold;
  int timeout;
};

const PhoneConfig phoneConfigs[2] = {
    {150, 80, 600},
    {150, 80, 600}};

struct PhoneState {
  bool isOffHook;
  int pulseCount;
  bool inPulse;
  unsigned long lastPulseTime;
  bool isActuallyHangingUp; //distinguish pulse vs hangup
};

PhoneState phoneStates[2] = {
  {false, 0, false, 0, false},
  {false, 0, false, 0, false}
};

bool globalRelayState = false;
unsigned long lastRelayAction = 0;
const int RELAY_STABILITY_PAUSE = 1000; // Wait 1s after connection before allowing break

void setup() {
  Serial.begin(9600);
  pinMode(relaysPin, OUTPUT);
  digitalWrite(relaysPin, LOW);
}

void loop() {
  int valT1 = analogRead(measurePinT1);
  int valT2 = analogRead(measurePinT2);

  // 1. Process the lines
  processLine(valT1, T1);
  processLine(valT2, T2);

  // 2. Control the Relay
  updateRelayLogic();
}

//------------------------ LINE PROCESSING ------------------------//
void processLine(int val, int phoneID) {
  const PhoneConfig &config = phoneConfigs[phoneID];
  PhoneState &state = phoneStates[phoneID];

  // LIFT DETECTION
  if (!state.isOffHook && val > config.pickupThreshold) {
    state.isOffHook = true;
    state.pulseCount = 0;
    Serial.print("Phone ");
    Serial.print(phoneID);
    Serial.println(" [OFF-HOOK]");
  }

  // PULSE & HANGUP LOGIC
  if (state.isOffHook) {
    // Detection of a pulse/break
    if (val < config.hangupThreshold && !state.inPulse) {
      state.inPulse = true;
      state.lastPulseTime = millis();
    }
    // Detection of a re-connect
    else if (val > config.pickupThreshold && state.inPulse) {
      state.inPulse = false;
      state.pulseCount++;
      state.lastPulseTime = millis();
    }

    // Timeout Logic: Is the silence a Digit or a Hang-up?
    if (millis() - state.lastPulseTime > config.timeout) {
      if (state.inPulse) {
        // Line stayed low too long -> REAL HANGUP
        state.isOffHook = false;
        state.inPulse = false;
        state.pulseCount = 0;
        Serial.print("Phone ");
        Serial.print(phoneID);
        Serial.println(" [ON-HOOK]");
      } else if (state.pulseCount > 0) {
        // Line stayed high -> DIGIT FINISHED
        int digit = (state.pulseCount == 10) ? 0 : state.pulseCount;
        Serial.print("Phone ");
        Serial.print(phoneID);
        Serial.print(" Dialed: ");
        Serial.println(digit);
        state.pulseCount = 0;
      }
    }
  }
}

//------------------------ RELAY CONTROL ------------------------//

void updateRelayLogic() {
  // A phone is "In Use" if it is Off-Hook and NOT currently in the middle of a
  // pulse break
  bool t1Active = phoneStates[T1].isOffHook && !phoneStates[T1].inPulse;
  bool t2Active = phoneStates[T2].isOffHook && !phoneStates[T2].inPulse;

  bool targetState = (t1Active && t2Active);

  // Add a lockout: Don't flip relay if someone is actively pulsing/dialing
  bool anyoneIsPulsing = phoneStates[T1].inPulse || phoneStates[T2].inPulse;

  if (!anyoneIsPulsing && targetState != globalRelayState) {
    // Extra debounce: Ensure we don't rapid-fire the relay
    if (millis() - lastRelayAction > 500) {
      globalRelayState = targetState;
      digitalWrite(relaysPin, globalRelayState ? HIGH : LOW);
      lastRelayAction = millis();
      Serial.println(globalRelayState ? ">>> CONNECTED" : ">>> DISCONNECTED");
    }
  }
}