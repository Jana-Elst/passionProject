//--- CONFIG
const String DeviceName = "T1";

//------------------------ SETUP ------------------------//
void setup() {
  Serial.begin(9600);
}

//------------------------ LOOP ------------------------//
void loop() {
  //--- 0. Handshake
  // this should loop till the handshake is done
  while (!handshake()) {
    delay(100);
  }
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