---
title: '#17 coding the arduino(s)'
description: |
    ???
pubDate: 'Jan 22 2026'
heroImage: ../../assets/pictures/20260122-header.png
sources:

gemini: 

components: 

links: 
---
Yesterday, I successfully made my 9V DC circuit and ran some basic tests using old Arduino code. Today’s goal was more ambitious: writing the full production code to track the phone's various states and prepare the data to be sent to the pi via the Serial Monitor.

I hit a brief moment of panic when the hook detection and dialing weren't registering at all. I worried I did something wrong with the circuit, but the fix was actually quite simple. First, I realized I needed to use analog pins instead of digital ones to get a more granular reading of the voltage  and spikes. Second, I had moved my measurement points from the positive to the negative side of the circuit, which inverted my logic. Now, when the phone is on-hook, the value reads near 0 instead of 900. After accounting for these hardware shifts in the code, everything worked perfectly.

## Functional Requirements
The Arduino code is designed to handle three main tasks:

**Hook Detection:** Monitor if the handset is on or off the hook.

**Pulse Dialing:** Detect and count the pulses to determine which number was dialed.

**Relay Control:** Open and close the relays to manage the bell and the audio connection.

## Communication Protocol
To communicate with the Raspberry Pi, I established a set of Serial codes. This allows the Pi to act as the "brain" while the Arduino handles the real-time hardware sensing.

**Outgoing signals to the Pi:**

**TX_OFFH:** Phone picked up.

**TX_ONH:** Phone hung up.

**TX_N[0-9]:** Number dialed (e.g., TX_N5 for digit 5).

note: X stands for the phone number. T1 is phone 1, T2 is phone 2.

**Incoming commands from the Pi:**

**R1_OPEN / R1_CLOSE:** Connect or disconnect the phone lines.

## The code
The code uses a threshold-based system to distinguish between a temporary "break" (a pulse during dialing) and a long "break" (hanging up the phone). By measuring the time the voltage stays low—using a timeout of 600ms—the code can accurately determine if the user is finished dialing a digit or has ended the call entirely.

````
struct PhoneConfig {
  int pickupThreshold;
  int hangupThreshold;
  int timeout;
};

const PhoneConfig phoneConfigs[2] = {
    // pickupThreshold (High/Rising), hangupThreshold (Low/Falling), timeout(ms)
    {45, 20, 600}, // T1
    {60, 30, 600}  // T2
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
````
````
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
````


So at the end of the day, I could manage the whole state of the both phones. And all the serial communication was prepared to be sent to the pi.