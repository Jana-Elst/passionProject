/*TO SLOW, combined with 20260118-2-sendSong on the pi*/

// Nano 33 IoT Audio Streamer
void setup() {
  Serial.begin(115200); 

  // Set the DAC resolution (Nano IoT supports up to 10-bit)
  analogWriteResolution(10); 
  while (!Serial); 
}

void loop() {
  if (Serial.available() > 0) {
    int audioSample = Serial.read();

    // Map the 8-bit signal (0-255) to the 10-bit DAC (0-1023)
    int dacValue = map(audioSample, 0, 255, 0, 1023);
    analogWrite(A0, dacValue);

    // This delay controls the "Sample Rate"
    // For 8000Hz audio, we need 125 microseconds
    delayMicroseconds(120); 
  }
}