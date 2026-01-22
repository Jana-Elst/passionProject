//--- PINS
const int relaysPin = 10;
const int measurePinT1 = A1;
const int measurePinT2 = A2;

// PHONES Id's
#define T1 0
#define T2 1

//--- CONFIG
// Config Structure
struct PhoneConfig
{
  int pickupThreshold; // Voltage to consider "Off-Hook"
  int hangupThreshold; // Voltage to consider "On-Hook"
  int timeout;         // For pulse dialing later
};

const PhoneConfig phoneConfigs[2] = {
    {150, 80, 600}, // T1
    {150, 80, 600}  // T2
};

// Timing for Relay Stability
unsigned long lastRelaySwitchTime = 0;
const int debounceDelay = 200;

//--- STATES / VARIABLES
// State Structure
struct PhoneState
{
  bool isOffHook;
  int pulseCount;
  bool inPulse;
  unsigned long lastPulseTime;
};

PhoneState phoneStates[2] = {
    {false, 0, false, 0}, // T1
    {false, 0, false, 0}  // T2
};

bool globalRelayState = false;

//------------------------ SETUP ------------------------//
void setup()
{
  Serial.begin(9600);
  pinMode(relaysPin, OUTPUT);
  digitalWrite(relaysPin, LOW);
}

//------------------------ LOOP ------------------------//
void loop()
{
  // 1. Read values
  int valT1 = analogRead(measurePinT1);
  int valT2 = analogRead(measurePinT2);

  // 2. Detect Hook States
  hookStateDetection(valT1, T1);
  hookStateDetection(valT2, T2);

  // 3. Manage Relay based on states
  switchRelays();

  // 4. Debugging
  static unsigned long lastLog = 0;
  if (millis() - lastLog > 500)
  {
    printDebug(valT1, valT2);
    lastLog = millis();
  }
}

//------------------------ Functions ------------------------//
void hookStateDetection(int val, int phoneID)
{
  const PhoneConfig &config = phoneConfigs[phoneID];
  PhoneState &state = phoneStates[phoneID];
  bool prev = state.isOffHook;

  // Hysteresis Logic
  if (!state.isOffHook && val > config.pickupThreshold)
  {
    state.isOffHook = true;
  }
  else if (state.isOffHook && val < config.hangupThreshold)
  {
    state.isOffHook = false;
  }

  if (state.isOffHook != prev)
  {
    Serial.print("Phone ");
    Serial.print(phoneID);
    Serial.println(state.isOffHook ? " [OFF-HOOK]" : " [ON-HOOK]");
  }
}

void switchRelays()
{
  // Logic: Both phones must be off-hook to engage relay
  bool targetState = (phoneStates[T1].isOffHook && phoneStates[T2].isOffHook);

  if (targetState != globalRelayState)
  {
    if (millis() - lastRelaySwitchTime > debounceDelay)
    {
      globalRelayState = targetState;
      lastRelaySwitchTime = millis();

      digitalWrite(relaysPin, globalRelayState ? HIGH : LOW);
      Serial.println(globalRelayState ? ">>> RELAY HIGH" : ">>> RELAY LOW");
    }
  }
}