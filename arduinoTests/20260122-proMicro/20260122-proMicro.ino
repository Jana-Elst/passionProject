/*
THINGS THE PI SHOULD KNOW:
                                                                CODES IN SERIAL
MONITOR
  - When a phone goes OFF-HOOK                                  TX_OFFH
  - When a phone goes ON-HOOK                                   TX_ONH
  - When a phone DIALS a DIGIT (0-9)                            TX_N1   ...

Things the PI can do:
  - Connect/Disconnect the two phone lines via a relay          (R1_ON / R1_OFF)
*/

//--- PINS
const int relaysPin = 10;
const int measurePinT1 = A1;
const int measurePinT2 = A2;

#define T1 0
#define T2 1

//--- CONFIG
const String DeviceName = "MAIN";

struct PhoneConfig {
  int pickupThreshold;
  int hangupThreshold;
  int timeout;
};

const PhoneConfig phoneConfigs[2] = {
    // pickupThreshold, hangupThreshold, timeout(ms)
    {150, 80, 600}, // T1
    {150, 80, 600}  // T2
};

//--- STATE & VARIABLES
struct PhoneState {
  bool isOffHook;
  int pulseCount;
  bool inPulse; // currently in a pulse break
  unsigned long lastPulseTime;
  bool isActuallyHangingUp; // distinguish pulse vs hangup
};

PhoneState phoneStates[2] = {
    // isOffHook, pulseCount, inPulse, lastPulseTime, isActuallyHangingUp
    {false, 0, false, 0, false}, // T1
    {false, 0, false, 0, false}  // T2
};

bool globalRelayState = false;
unsigned long lastRelayAction = 0;
const int RelayStabilityPause =
    200; // Wait after connection before allowing break (ms)

//------------------------ SETUP ------------------------//
void setup() {
  Serial.begin(9600);
  pinMode(relaysPin, OUTPUT);
  digitalWrite(relaysPin, LOW);
}

//------------------------ LOOP ------------------------//
void loop() {
  //--- 0. Handshake
  // this should loop till the handshake is done
  while (!handshake()) {
    delay(100);
  }

  //--- 1. Read the lines
  int valueT1 = analogRead(measurePinT1);
  int valueT2 = analogRead(measurePinT2);

  //--- 2. Get all information from the lines
  // On/off hook state & dialed digits
  processLine(valueT1, T1);
  processLine(valueT2, T2);

  //--- 3. Control the Relay
  controlRelay();
}

//------------------------ Give handshake to the PI ------------------------//
bool handshake() {
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim(); // Remove any whitespace/newlines

    // When the Pi asks "IDENTIFY", send back the name
    if (incoming == "IDENTIFY") {
      Serial.println(DeviceName);

      //and send the current state of the lines
      if (phoneStates[T1].isOffHook) {
        Serial.println("T1_OFFH");
      } else {
        Serial.println("T1_ONH");
      }
      if (phoneStates[T2].isOffHook) {
        Serial.println("T2_OFFH");
      } else {
        Serial.println("T2_ONH");
      }

      return true;
    }
  }

  return false;
}

//------------------------ LINE PROCESSING ------------------------//
void processLine(int value, int phoneID) {
  const PhoneConfig &config = phoneConfigs[phoneID];
  PhoneState &state = phoneStates[phoneID];

  // Off-Hook Detection
  if (!state.isOffHook && value > config.pickupThreshold) {
    state.isOffHook = true;
    state.pulseCount = 0;
    Serial.print("T");
    Serial.print(phoneID + 1);
    Serial.println("_OFFH");
  }

  // Dial & On-Hook Detection
  if (state.isOffHook) {
    // Detection of a pulse
    if (value < config.hangupThreshold && !state.inPulse) {
      state.inPulse = true;
      state.lastPulseTime = millis();
    }

    // Count the pulses
    else if (value > config.pickupThreshold && state.inPulse) {
      state.inPulse = false;
      state.pulseCount++;
      state.lastPulseTime = millis();
    }

    // Is the pulse a Digit or a Hang-up?
    if (millis() - state.lastPulseTime > config.timeout) {
      if (state.inPulse) // inPulse means the voltage is low -> doesn't go back
                         // up? => HANGUP
      {
        state.isOffHook = false;
        state.inPulse = false;
        state.pulseCount = 0;
        Serial.print("T");
        Serial.print(phoneID + 1);
        Serial.println("_ONH");
      } else if (state.pulseCount >
                 0) // Line stayed high & pulseCount > 0 -> DIGIT FINISHED
      {
        int digit = (state.pulseCount == 10) ? 0 : state.pulseCount;
        Serial.print("T");
        Serial.print(phoneID + 1);
        Serial.print("_N");
        Serial.println(digit);
        state.pulseCount = 0;
      }
    }
  }
}

//------------------------ RELAY CONTROL ------------------------//
//--- THIS SHOULD BE CHANGING BASED WHAT THE PI IS SENDING ---//
void controlRelay() {
  // A phone is "In Use" if it is Off-Hook and NOT currently in the middle of a
  // pulse break
  bool t1Active = phoneStates[T1].isOffHook && !phoneStates[T1].inPulse;
  bool t2Active = phoneStates[T2].isOffHook && !phoneStates[T2].inPulse;

  bool enableRelay = (t1Active && t2Active);

  // Add a lockout: Don't flip relay if someone is actively pulsing/dialing
  bool anyoneIsPulsing = phoneStates[T1].inPulse || phoneStates[T2].inPulse;

  if (!anyoneIsPulsing && enableRelay != globalRelayState) {
    // Extra debounce: Ensure we don't rapid-fire the relay
    if (millis() - lastRelayAction > RelayStabilityPause) {
      globalRelayState = enableRelay;
      digitalWrite(relaysPin, globalRelayState ? HIGH : LOW);
      lastRelayAction = millis();
      Serial.println(globalRelayState ? ">>> PHONES CONNECTED"
                                      : ">>> PHONES DISCONNECTED");
    }
  }
}