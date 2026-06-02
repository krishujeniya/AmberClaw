/*
 * AmberClaw AI OS - Hardware Node Firmware (Arduino/ESP)
 * 
 * This is a simple command-response firmware that allows AmberClaw 
 * to control hardware via Serial.
 */

const int STATUS_LED = 13;

void setup() {
  Serial.begin(9600);
  pinMode(STATUS_LED, OUTPUT);
  
  // Signal ready
  digitalWrite(STATUS_LED, HIGH);
  delay(500);
  digitalWrite(STATUS_LED, LOW);
  
  Serial.println("AMBER_NODE_READY");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "LED_ON") {
      digitalWrite(STATUS_LED, HIGH);
      Serial.println("OK: LED IS ON");
    } 
    else if (command == "LED_OFF") {
      digitalWrite(STATUS_LED, LOW);
      Serial.println("OK: LED IS OFF");
    }
    else if (command == "GET_TEMP") {
      // Mock sensor data
      float temp = 22.5 + (random(0, 10) / 10.0);
      Serial.print("TEMP:");
      Serial.println(temp);
    }
    else {
      Serial.print("ERROR: UNKNOWN_COMMAND:");
      Serial.println(command);
    }
  }
}
