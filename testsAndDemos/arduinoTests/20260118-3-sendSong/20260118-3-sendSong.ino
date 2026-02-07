// void setup() {
//   Serial.begin(500000); 
//   analogWriteResolution(10); 
//   while (!Serial); 
// }

// void loop() {
//   if (Serial.available() > 0) {
//     // Read byte and immediately bit-shift 
//     // (Value 0-255 becomes 0-1020, which is nearly 10-bit 1023)
//     int sample = Serial.read() << 2; 

//     analogWrite(A0, sample);

//     // Reduced delay to account for code execution time
//     // Try values between 100 and 115 to find the "perfect" speed
//     delayMicroseconds(110); 
//   }
// }

// Buffer size should match the chunk_size in Python
const int CHUNK_SIZE = 64; 
uint8_t audioBuffer[CHUNK_SIZE];

void setup() {
  // Nano 33 IoT USB Serial is actually "Virtual" - speed doesn't matter much, 
  // but we set it high just in case.
  Serial.begin(1000000); 
  analogWriteResolution(10);
  while (!Serial);
}

void loop() {
  // If at least one chunk is ready in the Serial buffer
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