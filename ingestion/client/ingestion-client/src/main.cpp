#include <Arduino.h>
#include "certs.h"
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_task_wdt.h>

#define TINY_GSM_MODEM_SIM7670G
#define TINY_GSM_RX_BUFFER 1024

#include <TinyGsmClient.h>

#ifndef TINY_GSM_FORK_LIBRARY
#error "Please use LilyGO's forked TinyGSM. Copy the lib directory from https://github.com/Xinyuan-LilyGO/LilyGO-T-A76XX to your Arduino libraries."
#endif

#define CELLULAR_APN "giffgaff.com"

Preferences preferences;
String mqtt_user;
String mqtt_pass;
String device_id;
String mqtt_broker;
String wifi_ssid;
String wifi_pass;
bool ledToggle;
bool forcePublish = false;

#define MODEM_BAUDRATE                  (115200)
#define MODEM_TX_PIN                    (11)
#define MODEM_RX_PIN                    (10)
#define MODEM_DTR_PIN                   (9)
#define MODEM_RING_PIN                  (3)
#define MODEM_RESET_PIN                 (17)
#define MODEM_RESET_LEVEL               LOW
#define SerialAT                        Serial1

#define BOARD_PWRKEY_PIN                (18)
#define BOARD_LED_PIN                   (12)
#define LED_ON                          (LOW)
#define LED_OFF                         (HIGH)

#define BOARD_BAT_ADC_PIN               (4)
#define BOARD_SOLAR_ADC_PIN             (5)

#define MODEM_GPS_ENABLE_GPIO           (4)
#define MODEM_GPS_ENABLE_LEVEL          (1)

#define MODEM_POWERON_PULSE_WIDTH_MS    (100)
#define EARTH_RADIUS_METERS             6371000.0

#define SerialMon Serial

#ifdef DUMP_AT_COMMANDS
#include <StreamDebugger.h>
StreamDebugger debugger(SerialAT, SerialMon);
TinyGsm modem(debugger);
#else
TinyGsm modem(SerialAT);
#endif

TinyGsmClient cellClient(modem);
WiFiClientSecure wifiClient;
PubSubClient mqtt(wifiClient);

enum ConnMode { CONN_NONE, CONN_WIFI, CONN_CELL };
ConnMode activeConn = CONN_NONE;

String topicPublish;
String topicSubscribe;

double last_lat = 0.0;
double last_lng = 0.0;
double last_update_time = 0.0;
bool is_first_fix = true;
int delay_interval = 1000;

// ===== Topics =====

void updateMqttTopics()
{
  topicPublish = "entity/" + device_id + "/telemetry";
  topicSubscribe = "entity/" + device_id + "/commands";
  Serial.println("Pub: " + topicPublish);
  Serial.println("Sub: " + topicSubscribe);
}

// ===== Preferences =====

void setPreference(const char* name, const char* key, const String& value)
{
  preferences.begin(name, false);
  preferences.putString(key, value);
  preferences.end();
}

// ===== GPS =====

double haversine(double lat1, double lng1, double lat2, double lng2)
{
  double dLat = (lat2 - lat1) * PI / 180.0;
  double dLon = (lng2 - lng1) * PI / 180.0;
  double rLat1 = lat1 * PI / 180.0;
  double rLat2 = lat2 * PI / 180.0;
  double a = sin(dLat/2)*sin(dLat/2) + sin(dLon/2)*sin(dLon/2)*cos(rLat1)*cos(rLat2);
  return EARTH_RADIUS_METERS * 2 * atan2(sqrt(a), sqrt(1-a));
}

struct GNSSInfo { bool hasFix; double latitude, longitude; float altitude, speed, course, hdop; int satsUsed; };

String getFieldAt(String rawData, int n)
{
  int commaIndex = -1;
  for (int i = 0; i < n; i++) commaIndex = rawData.indexOf(",", commaIndex + 1);
  int fieldStart = commaIndex + 1;
  int fieldEnd = rawData.indexOf(",", fieldStart);
  return fieldEnd == -1 ? rawData.substring(fieldStart) : rawData.substring(fieldStart, fieldEnd);
}

GNSSInfo extractGPS(String rawData)
{
  GNSSInfo data;
  if (rawData.indexOf('N') == -1 && rawData.indexOf('S') == -1) { data.hasFix = false; return data; }
  data.hasFix = true;
  data.latitude = getFieldAt(rawData, 5).toDouble();
  data.longitude = getFieldAt(rawData, 7).toDouble();
  if (getFieldAt(rawData, 6) == "S") data.latitude *= -1.0;
  if (getFieldAt(rawData, 8) == "W") data.longitude *= -1.0;
  data.altitude = getFieldAt(rawData, 11).toFloat();
  data.speed = getFieldAt(rawData, 12).toFloat();
  data.course = getFieldAt(rawData, 13).toFloat();
  data.hdop = getFieldAt(rawData, 15).toFloat();
  data.satsUsed = getFieldAt(rawData, 17).toInt();
  return data;
}

// ===== System =====

float readBatVoltage()
{
  return modem.getBattVoltage() / 1000.0f;
}

void blinkError(int times)
{
  for (int i = 0; i < times; i++) {
    digitalWrite(BOARD_LED_PIN, LED_ON);
    delay(100);
    digitalWrite(BOARD_LED_PIN, LED_OFF);
    delay(100);
  }
  delay(500);
}

// ===== MQTT Callbacks =====

void wifiMqttCallback(char* topic, byte* payload, unsigned int length)
{
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.printf("Message [%s]: %s\n", topic, message);
  if (strcmp(message, "ON") == 0) digitalWrite(BOARD_LED_PIN, LED_ON);
  if (strcmp(message, "OFF") == 0) digitalWrite(BOARD_LED_PIN, LED_OFF);
}

void cellMqttCallback(const char* topic, const uint8_t* payload, uint32_t len)
{
  char message[len + 1];
  memcpy(message, payload, len);
  message[len] = '\0';
  Serial.printf("Message [%s]: %s\n", topic, message);
  if (strcmp(message, "ON") == 0) digitalWrite(BOARD_LED_PIN, LED_ON);
  if (strcmp(message, "OFF") == 0) digitalWrite(BOARD_LED_PIN, LED_OFF);
}

// ===== Network =====

bool tryWifi()
{
  if (wifi_ssid == "default_ssid" || wifi_ssid.isEmpty()) return false;

  Serial.print("[WiFi] Connecting to " + wifi_ssid + "...");
  WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());
    wifiClient.setCACert(BROKER_CA_CERT);
    mqtt.setClient(wifiClient);
    activeConn = CONN_WIFI;
    return true;
  }

  Serial.println("\n[WiFi] Failed");
  WiFi.disconnect();
  return false;
}

void uploadCellCerts()
{
  modem.sendAT("+CFSGFIS=3,\"ca.crt\"");
  if (modem.waitResponse(3000) == 1) {
    Serial.println("[Cell] CA cert already on modem");
    return;
  }

  Serial.println("[Cell] Uploading CA cert to modem...");
  String cert = String(BROKER_CA_CERT);
  cert.trim();
  int certLen = cert.length();

  modem.sendAT("+CFSWFILE=3,\"ca.crt\",0," + String(certLen) + ",10000");
  if (modem.waitResponse(10000, "DOWNLOAD") != 1) {
    Serial.println("[Cell] Modem not ready for cert upload");
    return;
  }

  SerialAT.print(cert);
  if (modem.waitResponse(10000) == 1) {
    Serial.println("[Cell] CA cert uploaded successfully");
  } else {
    Serial.println("[Cell] CA cert upload failed");
  }
}

bool tryCell()
{
  Serial.println("[Cell] Waiting for network...");
  if (!modem.waitForNetwork(60000L)) {
    Serial.println("[Cell] Network failed");
    return false;
  }

  Serial.println("[Cell] Connecting GPRS...");
  if (!modem.gprsConnect(CELLULAR_APN, "", "")) {
    Serial.println("[Cell] GPRS failed");
    return false;
  }
  Serial.println("[Cell] Connected: " + modem.localIP().toString());

  // Configure SSL context 0
  modem.sendAT("+CSSLCFG=\"sslversion\",0,4");       // TLS 1.2
  modem.waitResponse();
  modem.sendAT("+CSSLCFG=\"cacert\",0,\"ca.crt\"");
  modem.waitResponse();
  modem.sendAT("+CSSLCFG=\"ignorertctime\",0,1");
  modem.waitResponse();

  // Initialise modem MQTT stack with SSL enabled
  modem.mqtt_begin(true);

  mqtt.setClient(cellClient);
  activeConn = CONN_CELL;
  return true;
}

bool isNetworkUp()
{
  if (activeConn == CONN_WIFI) return WiFi.status() == WL_CONNECTED;
  if (activeConn == CONN_CELL) return modem.isGprsConnected();
  return false;
}

void connectNetwork()
{
  if (!tryWifi()) {
    Serial.println("[Net] Falling back to cellular...");
    if (!tryCell()) {
      Serial.println("[Net] All connections failed, will retry in loop");
    }
  }
}

// ===== MQTT =====

bool isMqttConnected()
{
  if (activeConn == CONN_WIFI) return mqtt.connected();
  if (activeConn == CONN_CELL) return modem.mqtt_connected();
  return false;
}

bool mqttPublish(const String& topic, const char* payload)
{
  if (activeConn == CONN_WIFI) return mqtt.publish(topic.c_str(), payload);
  if (activeConn == CONN_CELL) return modem.mqtt_publish(0, topic.c_str(), payload);
  return false;
}

void mqttConnect()
{
  static unsigned long lastAttempt = 0;
  if (millis() - lastAttempt < 5000) return;
  lastAttempt = millis();

  if (!isNetworkUp()) {
    Serial.println("[Net] Connection dropped, reconnecting...");
    activeConn = CONN_NONE;
    connectNetwork();
    if (activeConn == CONN_NONE) return;
  }

  Serial.printf("[MQTT] Connecting via %s...\n", activeConn == CONN_WIFI ? "WiFi" : "Cell");

  if (activeConn == CONN_WIFI) {
    mqtt.setServer(mqtt_broker.c_str(), 8883);
    if (mqtt.connect(device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str())) {
      Serial.println("[MQTT] WiFi connected");
      mqtt.subscribe(topicSubscribe.c_str());
      forcePublish = true;
    } else {
      Serial.printf("[MQTT] WiFi failed rc=%d\n", mqtt.state());
    }
  } else {
    if (modem.mqtt_connect(0, mqtt_broker.c_str(), 8883,
                           device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str())) {
      Serial.println("[MQTT] Cell connected");
      modem.mqtt_set_callback(cellMqttCallback);
      modem.mqtt_subscribe(0, topicSubscribe.c_str());
      forcePublish = true;
    } else {
      Serial.println("[MQTT] Cell failed");
    }
  }
}

// ===== Serial provisioning =====

void handleSerialProvisioning()
{
  if (!Serial.available()) return;
  String input = Serial.readStringUntil('\n');
  input.trim();
  bool needsMqttReconnect = false;

  if (input.startsWith("SET_USER:")) {
    mqtt_user = input.substring(9);
    setPreference("mqtt-config", "user", mqtt_user);
    needsMqttReconnect = true;
    Serial.println("Success: User saved: " + mqtt_user);
  } else if (input.startsWith("SET_PASS:")) {
    mqtt_pass = input.substring(9);
    setPreference("mqtt-config", "pass", mqtt_pass);
    needsMqttReconnect = true;
    Serial.println("Success: Password saved.");
  } else if (input.startsWith("SET_ID:")) {
    device_id = input.substring(7);
    setPreference("mqtt-config", "dev_id", device_id);
    updateMqttTopics();
    needsMqttReconnect = true;
    Serial.println("Success: Device ID saved: " + device_id);
  } else if (input.startsWith("SET_BROKER:")) {
    mqtt_broker = input.substring(11);
    setPreference("mqtt-config", "broker", mqtt_broker);
    needsMqttReconnect = true;
    Serial.println("Success: Broker saved: " + mqtt_broker);
  } else if (input.startsWith("SET_SSID:")) {
    wifi_ssid = input.substring(9);
    setPreference("wifi-config", "ssid", wifi_ssid);
    Serial.println("Success: SSID saved: " + wifi_ssid);
  } else if (input.startsWith("SET_WPASS:")) {
    wifi_pass = input.substring(10);
    setPreference("wifi-config", "pass", wifi_pass);
    Serial.println("Success: WiFi password saved.");
  } else if (input == "FORCE_PUBLISH") {
    forcePublish = true;
    Serial.println("Success: Next GPS update will be published regardless of HDOP/distance.");
  } else if (input == "SHOW_CONFIG") {
    Serial.println("ID: " + device_id);
    Serial.println("User: " + mqtt_user);
    Serial.println("Broker: " + mqtt_broker);
    Serial.println("WiFi SSID: " + wifi_ssid);
    Serial.printf("Connection: %s\n",
      activeConn == CONN_WIFI ? "WiFi" :
      activeConn == CONN_CELL ? "Cell" : "None");
  } else if (input == "RESTART") {
    Serial.println("Restarting...");
    delay(1000);
    ESP.restart();
  }

  if (needsMqttReconnect) {
    Serial.println("[MQTT] Config changed, reconnecting...");
    if (activeConn == CONN_WIFI) mqtt.disconnect();
    else if (activeConn == CONN_CELL) modem.mqtt_disconnect();
  }
}

// ===== Setup =====

void setup()
{
  Serial.begin(115200);
  Serial.setTimeout(100);

  esp_task_wdt_init(30, true);
  esp_task_wdt_add(NULL);

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

  if (device_id == "G-S3-GENERIC") {
    Serial.println("[WARN] Device ID not configured! Use SET_ID:<uuid>");
  }
  if (mqtt_broker == "mqtt_broker") {
    Serial.println("[WARN] Broker not configured! Use SET_BROKER:<ip>");
  }
  if (mqtt_user == "default_user") {
    Serial.println("[WARN] MQTT user not configured! Use SET_USER:<username>");
  }

  pinMode(BOARD_LED_PIN, OUTPUT);
  digitalWrite(BOARD_LED_PIN, LED_OFF);

  if (device_id == "G-S3-GENERIC" || mqtt_broker == "mqtt_broker") {
    blinkError(5);
  }

  pinMode(MODEM_RESET_PIN, OUTPUT);
  digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);
  delay(100);
  digitalWrite(MODEM_RESET_PIN, MODEM_RESET_LEVEL);
  delay(2600);
  digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);

  pinMode(MODEM_DTR_PIN, OUTPUT);
  digitalWrite(MODEM_DTR_PIN, LOW);

  pinMode(BOARD_PWRKEY_PIN, OUTPUT);
  digitalWrite(BOARD_PWRKEY_PIN, LOW);
  delay(100);
  digitalWrite(BOARD_PWRKEY_PIN, HIGH);
  delay(MODEM_POWERON_PULSE_WIDTH_MS);
  digitalWrite(BOARD_PWRKEY_PIN, LOW);

  SerialAT.begin(115200, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  Serial.println("Starting modem...");
  delay(3000);

  int retry = 0;
  while (!modem.testAT(1000)) {
    Serial.print(".");
    if (retry++ > 30) {
      digitalWrite(BOARD_PWRKEY_PIN, HIGH);
      delay(MODEM_POWERON_PULSE_WIDTH_MS);
      digitalWrite(BOARD_PWRKEY_PIN, LOW);
      retry = 0;
    }
  }

  String modemName;
  while ((modemName = modem.getModemName()) == "UNKNOWN") {
    Serial.println("Waiting for modem...");
    delay(1000);
  }
  Serial.println("Modem: " + modemName);

  Serial.println("Enabling GPS...");
  while (!modem.enableGPS(MODEM_GPS_ENABLE_GPIO, MODEM_GPS_ENABLE_LEVEL)) delay(500);
  modem.setGPSBaud(115200);
  Serial.println("GPS enabled");

  uploadCellCerts();
  connectNetwork();

  // WiFi MQTT config (cell MQTT is configured per-connect via modem API)
  mqtt.setCallback(wifiMqttCallback);
  mqtt.setKeepAlive(60);
  mqtt.setSocketTimeout(15);
}

// ===== Loop =====

void loop()
{
  if (activeConn == CONN_WIFI && WiFi.status() != WL_CONNECTED) {
    Serial.println("[Net] WiFi signal lost! Forcing fallback process...");
    mqtt.disconnect();
    activeConn = CONN_NONE;
  }

  esp_task_wdt_reset();

  handleSerialProvisioning();

  if (!isMqttConnected()) mqttConnect();

  if (activeConn == CONN_WIFI) mqtt.loop();
  if (activeConn == CONN_CELL) modem.mqtt_handle();

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

      double distance = is_first_fix ? 0 : haversine(last_lat, last_lng, update.latitude, update.longitude);
      double currentTime = millis() / 1000.0;
      double timeDelta = currentTime - last_update_time;

      if ((update.hdop <= 5 && (distance > 5 || is_first_fix)) || forcePublish || timeDelta > 300)
      {
        JsonDocument doc;
        doc["lat"] = update.latitude;
        doc["lng"] = update.longitude;
        doc["spd"] = update.speed;
        doc["hdop"] = update.hdop;
        doc["sats"] = update.satsUsed;
        doc["dist"] = distance;
        doc["bat"] = readBatVoltage();

        char buffer[256];
        serializeJson(doc, buffer);

        if (mqttPublish(topicPublish, buffer)) {
          Serial.println("[MQTT] Published: " + String(buffer));
        } else {
          Serial.println("[MQTT] Publish failed");
        }

        last_lat = update.latitude;
        last_lng = update.longitude;
        is_first_fix = false;
        forcePublish = false;
        last_update_time = currentTime;
        delay_interval = 10000;
      }
      else
      {
        Serial.println("[GPS] Skipping (HDOP too high or distance too short)");
        delay_interval = 5000;
      }
    }
    else
    {
      digitalWrite(BOARD_LED_PIN, ledToggle ? LED_OFF : LED_ON);
      ledToggle = !ledToggle;
      Serial.println("[GPS] Waiting for fix...");
      delay_interval = 1000;
    }
  }
}