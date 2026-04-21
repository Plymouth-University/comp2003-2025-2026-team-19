#include <Arduino.h>

#define MODEM_BAUDRATE (115200)
#define MODEM_TX_PIN (11)
#define MODEM_RX_PIN (10)
#define MODEM_DTR_PIN (9)
#define MODEM_RING_PIN (3)
#define MODEM_RESET_PIN (17)
#define MODEM_RESET_LEVEL LOW
#define SerialAT Serial1

// --- Board Controls ---
#define BOARD_PWRKEY_PIN (18)
#define BOARD_LED_PIN (12)
#define LED_ON (LOW)
#define LED_OFF (HIGH)

// --- ADC / Sensors ---
#define BOARD_BAT_ADC_PIN (4)
#define BOARD_SOLAR_ADC_PIN (5)

// --- GPS Settings ---
#define MODEM_GPS_ENABLE_GPIO (4)
#define MODEM_GPS_ENABLE_LEVEL (1)

// --- Driver & Metadata ---
#define TINY_GSM_MODEM_SIM7670G

// --- Power Sequence Timings (ms) ---
#define MODEM_POWERON_PULSE_WIDTH_MS (100)
#define MODEM_POWEROFF_PULSE_WIDTH_MS (3000)
#define MODEM_START_WAIT_MS (3000)

// --- Mathematical constants ---
#define EARTH_RADIUS_METERS 6371000.0

// --- Previous GPS result ---
double last_lat = 0.0;
double last_lng = 0.0;
bool is_first_fix = true;

#define TINY_GSM_RX_BUFFER 1024 // Set RX buffer to 1Kb

// Set serial for debug console (to the Serial Monitor, default speed 115200)
#define SerialMon Serial

#include <TinyGsmClient.h>

#ifdef DUMP_AT_COMMANDS // if enabled it requires the streamDebugger lib
#include <StreamDebugger.h>
StreamDebugger debugger(SerialAT, SerialMon);
TinyGsm modem(debugger);
#else
TinyGsm modem(SerialAT);
#endif

struct GNSSInfo
{
  bool hasFix;
  int fixMode;
  double latitude;
  double longitude;
  float altitude;
  float speed;
  float course;
  float hdop;
  int satsUsed;
};

String getFieldAt(String rawData, int n);
GNSSInfo extractGPS(String rawData);
double haversine(double lat1, double lng1, double lat2, double lng2);

double haversine(double lat1, double lng1, double lat2, double lng2)
{
  // Convert degrees to radians
  double dLat = (lat2 - lat1) * PI / 180.0;
  double dLon = (lng2 - lng1) * PI / 180.0;

  // Convert latitudes to radians for the cosine calculation
  double rLat1 = lat1 * PI / 180.0;
  double rLat2 = lat2 * PI / 180.0;

  // Haversine formula
  double a = sin(dLat / 2) * sin(dLat / 2) + sin(dLon / 2) * sin(dLon / 2) * cos(rLat1) * cos(rLat2);

  double c = 2 * atan2(sqrt(a), sqrt(1 - a));

  // Return distance in meters
  return EARTH_RADIUS_METERS * c;
}

GNSSInfo extractGPS(String rawData)
{
  // rawData format: FixMode,GPS_Sats,GLO_Sats,BEI_Sats,GAL_Sats,Lat,N/S,Lon,E/W,Date,Time,Alt,Speed,Course,PDOP,HDOP,VDOP,SatsUsed
  GNSSInfo data;

  if (rawData.indexOf('N') == -1 && rawData.indexOf('S') == -1)
  {
    data.hasFix = false;
    return data;
  }

  data.hasFix = true;

  data.latitude = getFieldAt(rawData, 5).toDouble();
  data.longitude = getFieldAt(rawData, 7).toDouble();

  String latDirection = getFieldAt(rawData, 6);
  String lonDirection = getFieldAt(rawData, 8);

  if (latDirection == "S")
    data.latitude *= -1.0;
  if (lonDirection == "W")
    data.longitude *= -1.0;

  data.altitude = getFieldAt(rawData, 11).toFloat();
  data.speed = getFieldAt(rawData, 12).toFloat();
  data.course = getFieldAt(rawData, 13).toFloat();
  data.hdop = getFieldAt(rawData, 15).toFloat();
  data.satsUsed = getFieldAt(rawData, 17).toInt();

  return data;
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

void setup()
{
  Serial.begin(115200);

  // Set LED pin, ensure LED off
  pinMode(BOARD_LED_PIN, OUTPUT);
  digitalWrite(BOARD_LED_PIN, LED_OFF);

  // Set modem reset pin ,reset modem
  pinMode(MODEM_RESET_PIN, OUTPUT);
  digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);
  delay(100);
  digitalWrite(MODEM_RESET_PIN, MODEM_RESET_LEVEL);
  delay(2600);
  digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);

  // Pull down DTR to ensure the modem is not in sleep state
  Serial.printf("Set DTR pin %d LOW\n", MODEM_DTR_PIN);
  pinMode(MODEM_DTR_PIN, OUTPUT);
  digitalWrite(MODEM_DTR_PIN, LOW);

  // Turn on modem
  pinMode(BOARD_PWRKEY_PIN, OUTPUT);
  digitalWrite(BOARD_PWRKEY_PIN, LOW);
  delay(100);
  digitalWrite(BOARD_PWRKEY_PIN, HIGH);
  delay(MODEM_POWERON_PULSE_WIDTH_MS);
  digitalWrite(BOARD_PWRKEY_PIN, LOW);

  // Set modem baud
  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);

  Serial.println("Start modem...");
  delay(3000);

  int retry = 0;
  while (!modem.testAT(1000))
  {
    Serial.println(".");
    if (retry++ > 30)
    {
      digitalWrite(BOARD_PWRKEY_PIN, LOW);
      delay(100);
      digitalWrite(BOARD_PWRKEY_PIN, HIGH);
      delay(MODEM_POWERON_PULSE_WIDTH_MS);
      digitalWrite(BOARD_PWRKEY_PIN, LOW);
      retry = 0;
    }
  }
  Serial.println();
  delay(200);

  String modemName = "UNKNOWN";
  while (1)
  {
    modemName = modem.getModemName();
    if (modemName == "UNKNOWN")
    {
      Serial.println("Unable to obtain module information normally, try again");
      delay(1000);
    }
    else
    {
      Serial.print("Model Name:");
      Serial.println(modemName);
      break;
    }
    delay(5000);
  }

  // Print modem software version
  String res;
  modem.sendAT("+SIMCOMATI");
  modem.waitResponse(10000UL, res);
  Serial.println(res);

  Serial.println("Enabling GPS/GNSS/GLONASS");
  while (!modem.enableGPS(MODEM_GPS_ENABLE_GPIO, MODEM_GPS_ENABLE_LEVEL))
  {
    Serial.print(".");
  }
  Serial.println();
  Serial.println("GPS Enabled");

  // Set GPS Baud to 115200
  modem.setGPSBaud(115200);
}

void loop()
{
  Serial.println("Requesting current GPS/GNSS/GLONASS location");
  for (;;)
  {
    String rawData = modem.getGPSraw();

    GNSSInfo update = extractGPS(rawData);

    if (update.hasFix)
    {
      double distance = 0;
      if (is_first_fix)
      {
        is_first_fix = false;
      }
      else
      {
        distance = haversine(last_lat, last_lng, update.latitude, update.longitude);
      }
      last_lat = update.latitude;
      last_lng = update.longitude;
      SerialMon.printf("[GPS] Success! Lat: %f, Lng: %f, Alt: %f, Speed (knots): %f, Distance: %f, Course: %f, HDOP: %f, Sats used: %d\n", update.latitude, update.longitude, update.altitude, update.speed, distance, update.course, update.hdop, update.satsUsed);
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