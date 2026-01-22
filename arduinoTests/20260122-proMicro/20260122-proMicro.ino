//--- PINS
const int relaysPin = 10;
const int measurePinT1 = A1;
const int measurePinT2 = A2;

// PHONES
// Id's
#define T1 0
#define T2 1

// Config
struct PhoneConfig
{
  int onHookLimit;
  int pulseLowThreshold;
  int pulseHighThreshold;
  int timeout;
};

const PhoneConfig phoneConfigs[2] = {
    //onHookLimit, pulseLowThreshold, pulseHighThreshold, timeout
    {100, 200, 300, 600}, // T1
    {100, 300, 450, 600}  // T2
};

// State
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
bool currentStatePhonesAreOffHook = true;

void setup()
{
  Serial.begin(9600);
  pinMode(relaysPin, OUTPUT);
  digitalWrite(relaysPin, HIGH);
}

void loop()
{
  // 1. read phone values
  const int valT1 = analogRead(measurePinT1);
  const int valT2 = analogRead(measurePinT2);

  // Serial.print("T1: "); Serial.print(valT1);
  // Serial.print(" | T2: "); Serial.println(valT2);

  // 2. get hook state
  hookStateDetection(valT1, T1);
  hookStateDetection(valT2, T2);

  // 3. Switch Relays based on state
  switchRelays();
}

//------------------------ logic ------------------------//
void hookStateDetection(int val, int phoneID)
{
  const PhoneConfig &config = phoneConfigs[phoneID];
  PhoneState &state = phoneStates[phoneID];

  bool previousStateIsOffHook = state.isOffHook;
  if (val > config.pulseHighThreshold)
  {
    state.isOffHook = true;
    if (state.isOffHook != previousStateIsOffHook)
    {
      Serial.print(phoneID); Serial.println("[OFF-HOOK] Dialing enabled.");
    }
  }
  else if (val < config.onHookLimit)
  {
    state.isOffHook = false;
    if (state.isOffHook != previousStateIsOffHook)
    {
      Serial.print(phoneID); Serial.println("[ON-HOOK] Line closed.");
    }
  }
}

// bool phonesAreOffHook()
// {
//   bool prevPhonesWereOffHook = currentStatePhonesAreOffHook;
//   bool currentPhonesAreOffHook = phoneStates[T1].isOffHook && phoneStates[T2].isOffHook;
//   if (currentPhonesAreOffHook && !prevPhonesWereOffHook)
//   {
//     Serial.println("T1T2OFFH");
//   } else {
//     Serial.println("T1T2ONH");
//   }
//   return currentPhonesAreOffHook;
// }

void switchRelays()
{
  bool prevPhonesWereOffHook = currentStatePhonesAreOffHook;
  bool currentPhonesAreOffHook = phoneStates[T1].isOffHook && phoneStates[T2].isOffHook;

  if (currentPhonesAreOffHook != prevPhonesWereOffHook)
  {
    if (currentPhonesAreOffHook)
    {
      Serial.println("T1T2OFFH");
      // digitalWrite(relaysPin, HIGH);
      Serial.println("HIGH");

    }

    currentStatePhonesAreOffHook = currentPhonesAreOffHook;
    if (!currentPhonesAreOffHook) {
      Serial.println("T1T2ONH");
      // digitalWrite(relaysPin, LOW);
      Serial.println("LOW");
    }
  }
}