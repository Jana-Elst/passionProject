// Change the pin to A0
const int buzzerPin = A0; 

void setup() {
  pinMode(buzzerPin, OUTPUT);
}

void loop() {
  tone(buzzerPin, 1000); // Beep
  delay(150);
  noTone(buzzerPin);
  
  delay(100);

  tone(buzzerPin, 1000); // Beep
  delay(150);
  noTone(buzzerPin);

  delay(1000); // Wait 1 second
}