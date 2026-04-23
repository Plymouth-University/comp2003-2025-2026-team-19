#include <Arduino.h>
#include "certs.h"
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>

Preferences preferences;
String mqtt_user;
String mqtt_pass;
String device_id;
String mqtt_broker;
String wifi_ssid;
String wifi_pass;
bool ledToggle;

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

// TinyGsmClientSecure secureClient(modem);
// PubSubClient mqtt(secureClient);

String topicPublish;
String topicSubscribe;
const int port = 1883;

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

void updateMqttTopics()
{
  topicPublish = "entity/" + device_id + "/telemetry";
  topicSubscribe = "entity/" + device_id + "/commands";

  Serial.println("Topics Updated:");
  Serial.println("Pub: " + topicPublish);
  Serial.println("Sub: " + topicSubscribe);
}

void handleSerialProvisioning()
{
  if (Serial.available() > 0)
  {
    String input = Serial.readStringUntil('\n');
    input.trim();

    bool needsMqttReconnect = false;

    if (input.startsWith("SET_USER:"))
    {
      mqtt_user = input.substring(9);
      preferences.begin("mqtt-config", false);
      preferences.putString("user", mqtt_user);
      preferences.end();
      needsMqttReconnect = true;
      Serial.println("Success: MQTT User saved to NVS: " + mqtt_user);
    }
    else if (input.startsWith("SET_PASS:"))
    {
      mqtt_pass = input.substring(9);
      preferences.begin("mqtt-config", false);
      preferences.putString("pass", mqtt_pass);
      preferences.end();
      needsMqttReconnect = true;
      Serial.println("Success: MQTT Password saved to NVS.");
    }
    else if (input.startsWith("SET_ID:"))
    {
      device_id = input.substring(7);
      preferences.begin("mqtt-config", false);
      preferences.putString("dev_id", device_id);
      preferences.end();

      updateMqttTopics();
      needsMqttReconnect = true;

      Serial.println("Success: Device ID saved to NVS: " + device_id);
    }
    else if (input.startsWith("SET_BROKER:"))
    {
      mqtt_broker = input.substring(11);
      preferences.begin("mqtt-config", false);
      preferences.putString("broker", mqtt_broker);
      preferences.end();

      mqtt.setServer(mqtt_broker.c_str(), port);
      needsMqttReconnect = true;

      Serial.println("Success: MQTT Broker saved to NVS: " + mqtt_broker);
    }
    else if (input.startsWith("SET_SSID:"))
    {
      wifi_ssid = input.substring(9);
      preferences.begin("wifi-config", false);
      preferences.putString("ssid", wifi_ssid);
      preferences.end();
      Serial.println("Success: WiFi SSID set to: " + wifi_ssid);
    }
    else if (input.startsWith("SET_WPASS:"))
    {
      wifi_pass = input.substring(10);
      preferences.begin("wifi-config", false);
      preferences.putString("pass", wifi_pass);
      preferences.end();
      Serial.println("Success: WiFi Password set.");
    }
    else if (input == "RESTART")
    {
      Serial.println("Restarting device...");
      delay(1000);
      ESP.restart();
    }
    else if (input == "SHOW_CONFIG")
    {
      Serial.println("Current NVS Config:");
      Serial.println("ID: " + device_id);
      Serial.println("Mqtt User: " + mqtt_user);
      Serial.println("Mqtt Broker: " + mqtt_broker);
      Serial.println("WiFi SSID: " + wifi_ssid);
    }

    if (needsMqttReconnect)
    {
      Serial.println("[MQTT] Config changed. Forcing reconnection...");
      mqtt.disconnect();
    }
  }
}

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

void callback(char *topic, byte *payload, unsigned int length)
{
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");

  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.println(message);

  // Example: Turn on LED if message is "ON"
  if (strcmp(message, "ON") == 0)
    digitalWrite(BOARD_LED_PIN, LED_ON);
  if (strcmp(message, "OFF") == 0)
    digitalWrite(BOARD_LED_PIN, LED_OFF);
}

void setup()
{
  Serial.begin(115200);

  preferences.begin("mqtt-config", true);
  mqtt_user = preferences.getString("user", "default_user");
  mqtt_pass = preferences.getString("pass", "default_pass");
  device_id = preferences.getString("dev_id", "G-S3-GENERIC");
  mqtt_broker = preferences.getString("broker", "mqtt_broker");
  preferences.end();

  preferences.begin("wifi-config", true);
  wifi_ssid = preferences.getString("ssid", "default_ssid");
  wifi_pass = preferences.getString("pass", "default_wifi_pass");
  preferences.end();

  updateMqttTopics();

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

  unsigned long lastWifiCheck = 0;
  const unsigned long interval = 500;

  Serial.print("Connecting to WiFi: " + wifi_ssid);
  WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());

  for (;;)
  {
    if (WiFi.status() != WL_CONNECTED)
    {
      unsigned long currentMillis = millis();

      if (currentMillis - lastWifiCheck >= interval)
      {
        lastWifiCheck = currentMillis;
        Serial.print(".");
      }
    }
    else
    {
      Serial.println();
      Serial.println("WiFi connected with IP: " + WiFi.localIP().toString());
      break;
    }

    handleSerialProvisioning();
  }

  secureClient.setCACert(BROKER_CA_CERT);
  mqtt.setServer(mqtt_broker.c_str(), port);

  mqtt.setCallback(callback);
}

void mqttConnect()
{
  static unsigned long lastAttempt = 0;

  if (millis() - lastAttempt < 5000)
    return;
  lastAttempt = millis();
  Serial.printf("[MQTT] Disconnected - state: %d\n", mqtt.state());
  Serial.print("[MQTT] Connecting to MQTT...");
  if (mqtt.connect(device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str()))
  {
    Serial.println(" connected");
    JsonDocument doc;
    doc["message"] = "Device connected";
    char buffer[256];
    serializeJson(doc, buffer);
    mqtt.publish(topicPublish.c_str(), buffer);
  }
  else
  {
    Serial.print(" failed, rc=");
    Serial.print(mqtt.state());
    Serial.println();
  }
}

int delay_interval = 1000;

void loop()
{
  handleSerialProvisioning();

  if (!mqtt.connected())
  {
    mqttConnect();
  }
  mqtt.loop();

  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > delay_interval)
  {
    lastCheck = millis();

    String rawData = modem.getGPSraw();
    GNSSInfo update = extractGPS(rawData);

    if (update.hasFix)
    {
      digitalWrite(BOARD_LED_PIN, LED_ON);
      ledToggle = true;

      double distance = 0;
      if (!is_first_fix)
      {
        distance = haversine(last_lat, last_lng, update.latitude, update.longitude);
      }

      if (update.hdop <= 5 && (distance > 5 || is_first_fix))
      {
        JsonDocument doc;
        doc["lat"] = update.latitude;
        doc["lng"] = update.longitude;
        doc["spd"] = update.speed;
        doc["hdop"] = update.hdop;
        doc["sats"] = update.satsUsed;
        doc["dist"] = distance;

        char buffer[256];
        serializeJson(doc, buffer);
        mqtt.publish(topicPublish.c_str(), buffer);

        last_lat = update.latitude;
        last_lng = update.longitude;
        is_first_fix = false;
        Serial.println("[MQTT] Published GPS update: " + String(buffer));

        delay_interval = 10000;
      }
      else
      {
        Serial.println("[GPS] Fix acquired but HDOP too high or distance too short, skipping publish.");
        delay_interval = 5000;
      }
    }
    else
    {
      // Toggle the LED to indicate waiting for GPS fix
      if (!ledToggle)
      {
        digitalWrite(BOARD_LED_PIN, LED_ON);
        ledToggle = true;
      }
      else
      {
        digitalWrite(BOARD_LED_PIN, LED_OFF);
        ledToggle = false;
      }

      Serial.println("[GPS] Waiting for fix...");
      delay_interval = 1000;
    }
  }
}