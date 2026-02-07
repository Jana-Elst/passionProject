//connect with our pi and use following python code
/*
>> import serial
>> ser = serial.Serial('/dev/ttyACM0', 9600) //or a different port if needed
>> ser.write(bytes([14]))
*/

char receivedChar;
boolean newData = false;

void setup() {

  Serial.begin(9600);

  pinMode(14, OUTPUT);  
}

void loop() {
  recvInfo();
  lightLED();
}

void recvInfo() {
  if (Serial.available() > 0) {

    receivedChar = Serial.read();
    newData = true;
  }
  
}

void lightLED() {

  int led = receivedChar;

  while(newData == true) {

    digitalWrite(led, HIGH);
    delay(2000);
    digitalWrite(led, LOW);

    newData = false;
    
  }
  
}