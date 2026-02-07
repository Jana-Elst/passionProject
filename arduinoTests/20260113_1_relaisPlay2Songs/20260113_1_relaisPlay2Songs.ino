#include <SPI.h>
#include <SD.h>

#define SPEAKER_1 9
#define SPEAKER_2 10
#define SD_CS_PIN 4
#define SAMPLE_RATE 8000

const int RELAY1 = 7;
const int RELAY2 = 8; 

const int bufferSize = 64; 
uint8_t buf[bufferSize];
volatile int head = 0, tail = 0;

File file;
volatile bool playing = false;

// Variables for alternating logic
unsigned long lastSwitchTime = 0;
bool useSpeaker1 = true;

void setup() {
  Serial.begin(9600);
  delay(2000); 

  pinMode(RELAY1, OUTPUT);
  pinMode(RELAY2, OUTPUT);
  digitalWrite(RELAY1, LOW); //change for talking circuit
  digitalWrite(RELAY2, LOW); //change for talking circuit

  pinMode(SPEAKER_1, OUTPUT);
  pinMode(SPEAKER_2, OUTPUT);
  
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("SD Init Failed!");
    return;
  }

  // Timer 1: Enable PWM on BOTH Pin 9 (COM1A1) and Pin 10 (COM1B1)
  TCCR1A = _BV(COM1A1) | _BV(COM1B1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);

  // Timer 3: 8000Hz Interrupt
  noInterrupts();
  TCCR3A = 0;
  TCCR3B = _BV(WGM32) | _BV(CS30);
  OCR3A = 2000; 
  TIMSK3 = _BV(OCIE3A);
  interrupts();

  playFile("T1.wav");
}

void playFile(const char* fn) {
  file = SD.open(fn);
  if (file) { 
    file.seek(44); 
    playing = true; 
    Serial.println("Starting Playback...");
  }
}

ISR(TIMER3_COMPA_vect) {
  if (playing && head != tail) {
    uint8_t sample = buf[tail];
    
    if (useSpeaker1) {
      OCR1A = sample; // Audio to Pin 9
      OCR1B = 0;      // Silence Pin 10
    } else {
      OCR1B = sample; // Audio to Pin 10
      OCR1A = 0;      // Silence Pin 9
    }
    
    tail = (tail + 1) % bufferSize;
  }
}

void loop() {
  // 1. Alternating Logic
  if (millis() - lastSwitchTime >= 5000) {
    useSpeaker1 = !useSpeaker1;
    lastSwitchTime = millis();
    Serial.print("Switching to Speaker ");
    Serial.println(useSpeaker1 ? "1" : "2");
  }

  // 2. Buffer Refill Logic
  if (playing) {
    int next = (head + 1) % bufferSize;
    if (next != tail && file.available()) {
      buf[head] = file.read();
      head = next;
    }
    
    if (!file.available()) {
      playing = false;
      file.close();
      Serial.println("Playback Finished.");
    }
  }
}