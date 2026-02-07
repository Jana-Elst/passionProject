//FOUT
//The sound is noisy, crispy, to slow..
//sound is to silent

#include "SdFat.h"
#include <SPI.h>

#define SPEAKER_1 9
#define SPEAKER_2 10
#define SD_CS_PIN 4  // Use whatever CS pin you have wired
#define SAMPLE_RATE 8000

// We use 400 bytes per buffer. This is the "Safety Reservoir"
const int bufSize = 400; 
uint8_t buf1[bufSize], buf2[bufSize];
volatile int head1 = 0, tail1 = 0, head2 = 0, tail2 = 0;

SdFat sd;
File file1, file2;
bool playing1 = false, playing2 = false;

void setup() {
  pinMode(SPEAKER_1, OUTPUT);
  pinMode(SPEAKER_2, OUTPUT);

  // Start SD at full speed
  if (!sd.begin(SD_CS_PIN, SD_SCK_MHZ(16))) return;

  // PWM Setup
  TCCR1A = _BV(COM1A1) | _BV(COM1B1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);

  // Timer Setup (8kHz)
  TCCR3A = 0;
  TCCR3B = _BV(WGM32) | _BV(CS30);
  OCR3A = 16000000 / SAMPLE_RATE; 
  TIMSK3 = _BV(OCIE3A);

  file1 = sd.open("T1.wav");
  if(file1) { file1.seek(44); playing1 = true; }
  
  file2 = sd.open("T2.wav");
  if(file2) { file2.seek(44); playing2 = true; }
}

ISR(TIMER3_COMPA_vect) {
  if (playing1 && head1 != tail1) {
    OCR1A = buf1[tail1];
    tail1 = (tail1 + 1) % bufSize;
  }
  if (playing2 && head2 != tail2) {
    OCR1B = buf2[tail2];
    tail2 = (tail2 + 1) % bufSize;
  }
}

void loop() {
  // FILL BUFFER 1 (Read in chunks for speed)
  if (playing1) {
    while (((head1 + 1) % bufSize) != tail1 && file1.available()) {
      buf1[head1] = file1.read();
      head1 = (head1 + 1) % bufSize;
    }
  }

  // FILL BUFFER 2
  if (playing2) {
    while (((head2 + 1) % bufSize) != tail2 && file2.available()) {
      buf2[head2] = file2.read();
      head2 = (head2 + 1) % bufSize;
    }
  }
}