/*
THINGS THE PI SHOULD KNOW:
                                                                CODES IN SERIAL
MONITOR
  - When a phone goes OFF-HOOK                                  TX_OFFH
  - When a phone goes ON-HOOK                                   TX_ONH
  - When a phone DIALS a DIGIT (0-9)                            TX_N1   ...

Things the PI can do:
  - Connect/Disconnect the two phone lines via a relay          (R1_OPEN /
R1_CLOSE)
  - Open close bell circuit                                     (TX_BELL_START /
TX_BELL_STOP)
*/

//--- PINS
const int R1_PIN = 10;
const int R2_PIN = 8; // Bell 1
const int R3_PIN = 9; // Bell 2
const int measurePinT1 = A2;
const int measurePinT2 = A1;

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
    // pickupThreshold (High/Rising), hangupThreshold (Low/Falling), timeout(ms)
    {45, 20, 600}, // T1 (Off-hook: ~60-65, Bottom: ~10)
    {60, 30, 600}  // T2 (Off-hook: ~80-90)
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

const int RelayStabilityPause =
    200; // Wait after connection before allowing break (ms)

//------------------------ SETUP ------------------------//
void setup() {
  Serial.begin(1000000);
  pinMode(R1_PIN, OUTPUT);
  pinMode(R2_PIN, OUTPUT);
  pinMode(R3_PIN, OUTPUT);

  digitalWrite(R1_PIN, LOW);
  digitalWrite(R2_PIN, LOW);
  digitalWrite(R3_PIN, LOW);
}

//--- BELL STATE
struct BellState {
  bool isRinging;
  bool ringState;
  unsigned long lastRingTime;
  int pin;
};

BellState bellStates[2] = {
    {false, false, 0, R2_PIN}, // T1 (Bell 1)
    {false, false, 0, R3_PIN}  // T2 (Bell 2)
};

const unsigned long RING_ON_DURATION = 500;
const unsigned long RING_OFF_DURATION = 4000;

//--- STATE & VARIABLES
bool isConnected = false;

//------------------------ LOOP ------------------------//
void loop() {
  //--- 0. Handshake
  // If we haven't established a connection yet, wait for it.
  if (!isConnected) {
    while (!handshake()) {
      delay(100);
    }
    isConnected = true;
  }

  //--- 1. Check Serial Commands
  checkSerialCommands();

  //--- 1.5 Manage Bell
  manageBell(0); // T1
  manageBell(1); // T2

  //--- 2. Read the lines
  int valueT1 = analogRead(measurePinT1);
  int valueT2 = analogRead(measurePinT2);

  // Serial.print(valueT1);
  // Serial.print(" | ");
  // Serial.println(valueT2);

  //--- 3. Get all information from the lines
  // On/off hook state & dialed digits
  processLine(valueT1, T1);
  processLine(valueT2, T2);
}

//------------------------ Give handshake to the PI ------------------------//
bool handshake() {
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim(); // Remove any whitespace/newlines

    // When the Pi asks "IDENTIFY", send back the name
    if (incoming == "IDENTIFY") {
      Serial.println(DeviceName);

      // and send the current state of the lines
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

//------------------------ SERIAL COMMANDS ------------------------//
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    // "R1_OPEN" = Open the channel / Connect the phones (Relay HIGH)
    if (cmd == "R1_OPEN") {
      digitalWrite(R1_PIN, HIGH);
    }
    // "R1_CLOSE" = Close the channel / Disconnect (Relay LOW)
    else if (cmd == "R1_CLOSE") {
      digitalWrite(R1_PIN, LOW);
    }

    //--- RINGING
    // "T1_BELL_START"
    else if (cmd == "T1_BELL_START") {
      bellStates[0].isRinging = true;
      bellStates[0].ringState = false;
      bellStates[0].lastRingTime = 0;
    }
    // "T1_BELL_STOP"
    else if (cmd == "T1_BELL_STOP") {
      bellStates[0].isRinging = false;
      bellStates[0].ringState = false;
      digitalWrite(bellStates[0].pin, LOW);
    }
    // "T2_BELL_START"
    else if (cmd == "T2_BELL_START") {
      bellStates[1].isRinging = true;
      bellStates[1].ringState = false;
      bellStates[1].lastRingTime = 0;
    }
    // "T2_BELL_STOP"
    else if (cmd == "T2_BELL_STOP") {
      bellStates[1].isRinging = false;
      bellStates[1].ringState = false;
      digitalWrite(bellStates[1].pin, LOW);
    }
  }
}

//------------------------ BELL MANAGEMENT ------------------------//
void manageBell(int bellIndex) {
  BellState &bell = bellStates[bellIndex];

  if (!bell.isRinging)
    return;

  unsigned long currentMillis = millis();
  unsigned long interval =
      bell.ringState ? RING_ON_DURATION : RING_OFF_DURATION;

  if (currentMillis - bell.lastRingTime >= interval) {
    bell.lastRingTime = currentMillis;

    // Toggle state
    bell.ringState = !bell.ringState;

    if (bell.ringState) {
      // --- RING ON ---
      digitalWrite(bell.pin, HIGH);
    } else {
      // --- RING OFF ---
      digitalWrite(bell.pin, LOW);
    }
  }
}