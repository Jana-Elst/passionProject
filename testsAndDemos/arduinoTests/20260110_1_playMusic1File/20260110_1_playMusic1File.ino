#include <SPI.h>
#include <SD.h>

#define SPEAKER_1 9
#define SPEAKER_2 10
#define SD_CS_PIN 4  // MOVED from 10 to 4
#define SAMPLE_RATE 8000

const int bufferSize = 128; // Smaller buffers to save RAM for two files
uint8_t buf1[bufferSize], buf2[bufferSize];
volatile int head1 = 0, tail1 = 0, head2 = 0, tail2 = 0;

File file1, file2;
bool playing1 = false, playing2 = false;

void setup() {
  pinMode(SPEAKER_1, OUTPUT);
  pinMode(SPEAKER_2, OUTPUT);
  
  if (!SD.begin(SD_CS_PIN)) return;

  // Timer 1: Enable PWM on BOTH Pin 9 (COM1A1) and Pin 10 (COM1B1)
  TCCR1A = _BV(COM1A1) | _BV(COM1B1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);

  // Timer 3: 8000Hz Interrupt
  TCCR3A = 0;
  TCCR3B = _BV(WGM32) | _BV(CS30);
  OCR3A = 16000000 / SAMPLE_RATE; 
  TIMSK3 = _BV(OCIE3A);

  playT1("T1.wav");
  // playT2("T2.wav");
}

void playT1(const char* fn) {
  file1 = SD.open(fn);
  if (file1) { file1.seek(44); playing1 = true; }
}

// void playT2(const char* fn) {
//   file2 = SD.open(fn);
//   if (file2) { file2.seek(44); playing2 = true; }
// }

ISR(TIMER3_COMPA_vect) {
  // Handle Speaker 1 (Pin 9)
  if (playing1 && head1 != tail1) {
    OCR1A = buf1[tail1];
    tail1 = (tail1 + 1) % bufferSize;
  }
  
  // Handle Speaker 2 (Pin 10)
  // if (playing2 && head2 != tail2) {
  //   OCR1B = buf2[tail2];
  //   tail2 = (tail2 + 1) % bufferSize;
  // }
}

void loop() {
  // Refill Buffer 1
  if (playing1) {
    int next = (head1 + 1) % bufferSize;
    while (next != tail1 && file1.available()) {
      buf1[head1] = file1.read();
      head1 = next;
      next = (head1 + 1) % bufferSize;
    }
    if (!file1.available()) { playing1 = false; file1.close(); }
  }

  // Refill Buffer 2
  // if (playing2) {
  //   int next = (head2 + 1) % bufferSize;
  //   while (next != tail2 && file2.available()) {
  //     buf2[head2] = file2.read();
  //     head2 = next;
  //     next = (head2 + 1) % bufferSize;
  //   }
  //   if (!file2.available()) { playing2 = false; file2.close(); }
  // }
}