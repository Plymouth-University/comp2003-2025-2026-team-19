#include <Arduino.h>

#define MODEM_RX 10
#define MODEM_TX 11
#define MODEM_PWRKEY 18

#define SerialMon Serial // Connection to computer
#define SerialAT Serial1 // Connection to the SIM7670G

struct GNSSInfo
{
  bool hasFix;
  String latitude;
  String longitude;
};

String getFieldAt(String rawData, int n);
GNSSInfo extractGPS(String rawData);
String getResponse();

String getResponse()
{
  String resp = "";
  unsigned long timeout = millis() + 2000;
  while (millis() < timeout)
  {
    while (SerialAT.available() > 0)
    {
      resp += (char)SerialAT.read();
      timeout = millis() + 100; // extend while data is arriving
    }
  }

  return resp;
}

void setup()
{
  SerialMon.begin(115200);
  delay(1000);
  SerialMon.println("[BOOT] Starting up...");

  // Power on the modem
  pinMode(MODEM_PWRKEY, OUTPUT);
  digitalWrite(MODEM_PWRKEY, LOW);
  delay(100);
  digitalWrite(MODEM_PWRKEY, HIGH);
  delay(1000);
  digitalWrite(MODEM_PWRKEY, LOW);
  delay(5000);

  // Start serial communication with the modem
  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX);
  delay(500);

  // Turn command echo off
  // SerialAT.println("ATE0");
  // delay(200);
  // getResponse(); // flush

  SerialAT.println("AT+CGNSSMODE=15");
  delay(500);
  SerialAT.println("AT+CGNSSPWR?");
  delay(200);
  String resp = getResponse();
  if (resp.indexOf("+CGNSSPWR: 0") != -1) {
    SerialMon.println("[BOOT] GNSS is OFF. Powering on...");
    SerialAT.println("AT+CGNSSPWR=1");
    delay(500);
  } else {
    SerialMon.println("[BOOT] GNSS is already powered.");
  }

  // Power the GPS antenna
  SerialAT.println("AT+CGDRT=1,1");
  delay(200);
  SerialAT.println("AT+CGSETV=1,1");
  delay(500);

  SerialMon.println("[BOOT] Ready.");
}

String getFieldAt(String rawData, int n)
{
  int commaIndex = -1;

  for (int i = 0; i < n; i++)
  {
    commaIndex = rawData.indexOf(",", commaIndex + 1);
  }

  int fieldStart = commaIndex + 1;
  int fieldEnd = rawData.indexOf(",", fieldStart);

  if (fieldEnd == -1)
  {
    return rawData.substring(fieldStart);
  }

  return rawData.substring(fieldStart, fieldEnd);
}

GNSSInfo extractGPS(String rawData)
{
  GNSSInfo data;

  if (rawData.indexOf('N') == -1 && rawData.indexOf('S') == -1)
  {
    data.hasFix = false;
    return data;
  }
  
  data.hasFix = true;
  
  data.latitude = getFieldAt(rawData, 4);
  data.longitude = getFieldAt(rawData, 6);
  
  return data;
}

void loop()
{
  SerialMon.println("[GPS] Fetching location...");

  while (true)
  {
    SerialAT.println("AT+CGNSSINFO");
    String resp = getResponse();

    // SerialMon.println("[DEBUG] Raw: " + resp);

    if (resp.indexOf("ERROR") != -1 || resp.length() == 0)
    {
      SerialMon.println("[GPS] Modem error or no response");
      delay(10000);
      continue;
    }

    String prefix = "+CGNSSINFO: ";
    int start = resp.indexOf(prefix);
    if (start == -1)
    {
      SerialMon.println("[GPS] No CGNSSINFO in response");
      delay(10000);
      continue;
    }
    resp = resp.substring(start + prefix.length());

    GNSSInfo location = extractGPS(resp);

    if (location.hasFix)
    {
      SerialMon.printf("Success! Lat: %s, Lng: %s\n", location.latitude.c_str(), location.longitude.c_str());
      delay(10000);
      break;
    }
    else
    {
      SerialMon.println("[GPS] Waiting for fix...");
      delay(3000);
    }
  }
}

// void loop()
// {
//   // Pass commands from serial monitor to modem
//   if (SerialMon.available()) {
//     SerialAT.write(SerialMon.read());
//   }
//   // Print modem responses to serial monitor
//   if (SerialAT.available()) {
//     SerialMon.write(SerialAT.read());
//   }
// }

// void loop() {
//   SerialAT.println("AT");
//   delay(500);
//   SerialMon.println("[AT] " + getResponse());

//   SerialAT.println("AT+CGNSSPWR?");
//   delay(500);
//   SerialMon.println("[PWR] " + getResponse());

//   SerialAT.println("AT+CGNSSINFO");
//   delay(500);
//   SerialMon.println("[GPS] " + getResponse());

//   SerialAT.println("AT+CGNSSINFO=32");
//   delay(500);
//   SerialMon.println(getResponse());

//   delay(5000);
// }