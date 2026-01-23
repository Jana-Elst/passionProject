//--- CONFIG
// Name of the device
const String DeviceName = "T2";

// Buffer size should match the chunk_size in Python
const int CHUNK_SIZE = 64;
uint8_t audioBuffer[CHUNK_SIZE];

//------------------------ SETUP ------------------------//
void setup() {
  Serial.begin(1000000);
  analogWriteResolution(10);
  while (!Serial)
    ;
}

//------------------------ LOOP ------------------------//
void loop() {
  //--- 0. Handshake
  // this should loop till the handshake is done
  while (!handshake()) {
    delay(100);
  }

  //--- 1. Audio
  playAudio();
}

//------------------------ Give handshake to the PI ------------------------//
bool handshake() {
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim(); // Remove any whitespace/newlines

    // When the Pi asks "IDENTIFY", send back the name
    if (incoming == "IDENTIFY") {
      Serial.println(DeviceName);
      return true;
    }
  }

  return false;
}

//------------------------ Play audio ------------------------//
void playAudio() {
  if (Serial.available() >= CHUNK_SIZE) {
    // Read the entire chunk at once (high speed)
    Serial.readBytes(audioBuffer, CHUNK_SIZE);

    // Play the chunk
    for (int i = 0; i < CHUNK_SIZE; i++) {
      // Bit-shift 8-bit to 10-bit
      analogWrite(A0, audioBuffer[i] << 2);

      // The delay between samples is what determines speed
      // Lower this number (e.g., 110, 100, 90) to make it FASTER.
      delayMicroseconds(115);
    }
  }
}