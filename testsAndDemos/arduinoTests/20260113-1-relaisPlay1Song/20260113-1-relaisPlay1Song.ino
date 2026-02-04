#include <SPI.h>
#include <SD.h>

#define SPEAKER_1 9
#define SPEAKER_2 10
#define SD_CS_PIN 4
#define SAMPLE_RATE 8000

const int RELAY1 = 7;
const int RELAY2 = 8; 

// Use 'volatile' for variables shared between loop and ISR
const int bufferSize = 64; // Reduced to 64 to save RAM
uint8_t buf1[bufferSize];
volatile int head1 = 0, tail1 = 0;

File file1;
volatile bool playing1 = false;

void setup() {
  Serial.begin(9600);
  // Give the serial port time to stabilize
  delay(2000); 

  pinMode(RELAY1, OUTPUT);
  pinMode(RELAY2, OUTPUT);
  digitalWrite(RELAY1, HIGH);
  digitalWrite(RELAY2, HIGH);

  pinMode(SPEAKER_1, OUTPUT);
  
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("SD Init Failed!");
    return;
  }

  // Timer 1: PWM Setup for Pin 9
  TCCR1A = _BV(COM1A1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);

  // Timer 3: 8000Hz Interrupt
  // (Assuming you are using a Mega or Leonardo)
  noInterrupts(); // Disable interrupts during setup
  TCCR3A = 0;
  TCCR3B = _BV(WGM32) | _BV(CS30);
  OCR3A = 2000; // 16MHz / 8000Hz = 2000
  TIMSK3 = _BV(OCIE3A);
  interrupts();

  playT1("T1.wav");
}

void playT1(const char* fn) {
  file1 = SD.open(fn);
  if (file1) { 
    file1.seek(44); // Skip WAV header
    playing1 = true; 
    Serial.println("Playing T1...");
  }
}

ISR(TIMER3_COMPA_vect) {
  if (playing1 && head1 != tail1) {
    OCR1A = buf1[tail1];
    tail1 = (tail1 + 1) % bufferSize;
  }
}

void loop() {
  if (playing1) {
    int next = (head1 + 1) % bufferSize;
    // Only read if there is space in the buffer
    if (next != tail1 && file1.available()) {
      buf1[head1] = file1.read();
      head1 = next;
    }
    
    if (!file1.available()) {
      playing1 = false;
      file1.close();
      Serial.println("Done.");
    }
  }
}