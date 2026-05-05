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

#define MODEM_BAUDRATE (115200)
#define MODEM_TX_PIN (11)
#define MODEM_RX_PIN (10)
#define MODEM_DTR_PIN (9)
#define MODEM_RING_PIN (3)
#define MODEM_RESET_PIN (17)
#define MODEM_RESET_LEVEL LOW
#define SerialAT Serial1

#define BOARD_PWRKEY_PIN (18)
#define BOARD_LED_PIN (12)
#define LED_ON (LOW)
#define LED_OFF (HIGH)

#define BOARD_BAT_ADC_PIN (4)
#define BOARD_SOLAR_ADC_PIN (5)

#define MODEM_GPS_ENABLE_GPIO (4)
#define MODEM_GPS_ENABLE_LEVEL (1)

#define MODEM_POWERON_PULSE_WIDTH_MS (100)
#define EARTH_RADIUS_METERS 6371000.0

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

enum ConnMode
{
  CONN_NONE,
  CONN_WIFI,
  CONN_CELL
};
ConnMode activeConn = CONN_NONE;

String topicPublish;
String topicSubscribe;

static double last_lat = 0.0;
static double last_lng = 0.0;
static bool is_first_fix = true;

RTC_DATA_ATTR static double rtc_last_lat = 0.0;
RTC_DATA_ATTR static double rtc_last_lng = 0.0;
RTC_DATA_ATTR static bool rtc_is_first_fix = true;
RTC_DATA_ATTR static uint32_t rtc_secs_since_pub = 0; // tracks time across sleeps
RTC_DATA_ATTR static uint32_t rtc_last_sleep_s = 0;   // duration of last sleep
RTC_DATA_ATTR static int rtc_static_streak = 0;       // consecutive stationary polls
RTC_DATA_ATTR static int rtc_conn_mode = 0;           // persists activeConn across sleep
RTC_DATA_ATTR static bool rtc_force_publish = false;

#define GPS_FIX_TIMEOUT_MS 120000 // how long to wait for a fix after wake
#define SLEEP_MOVING_S 10        // actively moving
#define SLEEP_STATIC_S 20        // stationary, short streak
#define SLEEP_STATIC_LONG_S 90   // stationary, long streak
#define STATIC_STREAK_LONG 5     // readings before "long" sleep kicks in
#define PUBLISH_INTERVAL_S 300   // max time between publishes regardless of movement

// ===== Topics =====

void updateMqttTopics()
{
  topicPublish = "entity/" + device_id + "/telemetry";
  topicSubscribe = "entity/" + device_id + "/commands";
  Serial.println("Pub: " + topicPublish);
  Serial.println("Sub: " + topicSubscribe);
}

// ===== Preferences =====

void setPreference(const char *name, const char *key, const String &value)
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
  double a = sin(dLat / 2) * sin(dLat / 2) + sin(dLon / 2) * sin(dLon / 2) * cos(rLat1) * cos(rLat2);
  return EARTH_RADIUS_METERS * 2 * atan2(sqrt(a), sqrt(1 - a));
}

struct GNSSInfo
{
  bool hasFix;
  double latitude, longitude;
  float altitude, speed, course, hdop;
  int satsUsed;
};

String getFieldAt(String rawData, int n)
{
  int commaIndex = -1;
  for (int i = 0; i < n; i++)
    commaIndex = rawData.indexOf(",", commaIndex + 1);
  int fieldStart = commaIndex + 1;
  int fieldEnd = rawData.indexOf(",", fieldStart);
  return fieldEnd == -1 ? rawData.substring(fieldStart) : rawData.substring(fieldStart, fieldEnd);
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
  data.latitude = getFieldAt(rawData, 5).toDouble();
  data.longitude = getFieldAt(rawData, 7).toDouble();
  if (getFieldAt(rawData, 6) == "S")
    data.latitude *= -1.0;
  if (getFieldAt(rawData, 8) == "W")
    data.longitude *= -1.0;
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

int getBatteryPercentage(float voltage) {
  if (voltage >= 4.2) return 100;
  if (voltage >= 3.85) return map(voltage * 100, 385, 420, 50, 100);
  if (voltage >= 3.7)  return map(voltage * 100, 370, 385, 25, 50);
  if (voltage >= 3.3)  return map(voltage * 100, 330, 370, 5, 25);
  return 0; // Below 3.3V is effectively empty
}

void blinkError(int times)
{
  for (int i = 0; i < times; i++)
  {
    digitalWrite(BOARD_LED_PIN, LED_ON);
    delay(100);
    digitalWrite(BOARD_LED_PIN, LED_OFF);
    delay(100);
  }
  delay(500);
}

void goToSleep(uint32_t seconds)
{
  Serial.printf("[Sleep] GPS off, sleeping %u s (streak=%d)\n", seconds, rtc_static_streak);
  Serial.flush();

  rtc_last_sleep_s = seconds;

  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  esp_deep_sleep_start(); // ESP32-S3: ~10 µA; modem keeps LTE + MQTT alive
}

// ===== MQTT Callbacks =====

void wifiMqttCallback(char *topic, byte *payload, unsigned int length)
{
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.printf("Message [%s]: %s\n", topic, message);
  if (strcmp(message, "ON") == 0)
    digitalWrite(BOARD_LED_PIN, LED_ON);
  if (strcmp(message, "OFF") == 0)
    digitalWrite(BOARD_LED_PIN, LED_OFF);
}

void cellMqttCallback(const char *topic, const uint8_t *payload, uint32_t len)
{
  char message[len + 1];
  memcpy(message, payload, len);
  message[len] = '\0';
  Serial.printf("Message [%s]: %s\n", topic, message);
  if (strcmp(message, "ON") == 0)
    digitalWrite(BOARD_LED_PIN, LED_ON);
  if (strcmp(message, "OFF") == 0)
    digitalWrite(BOARD_LED_PIN, LED_OFF);
}

// ===== Network =====

bool tryWifi()
{
  if (wifi_ssid == "default_ssid" || wifi_ssid.isEmpty())
    return false;

  Serial.print("[WiFi] Connecting to " + wifi_ssid + "...");
  WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000)
  {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED)
  {
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
  if (modem.waitResponse(3000) == 1)
  {
    Serial.println("[Cell] CA cert already on modem");
    return;
  }

  Serial.println("[Cell] Uploading CA cert to modem...");
  String cert = String(BROKER_CA_CERT);
  cert.trim();
  int certLen = cert.length();

  modem.sendAT("+CFSWFILE=3,\"ca.crt\",0," + String(certLen) + ",10000");
  if (modem.waitResponse(10000, "DOWNLOAD") != 1)
  {
    Serial.println("[Cell] Modem not ready for cert upload");
    return;
  }

  SerialAT.print(cert);
  if (modem.waitResponse(10000) == 1)
  {
    Serial.println("[Cell] CA cert uploaded successfully");
  }
  else
  {
    Serial.println("[Cell] CA cert upload failed");
  }
}

bool tryCell()
{
  Serial.println("[Cell] Waiting for network...");
  if (!modem.waitForNetwork(60000L))
  {
    Serial.println("[Cell] Network failed");
    return false;
  }

  Serial.println("[Cell] Connecting GPRS...");
  if (!modem.gprsConnect(CELLULAR_APN, "", ""))
  {
    Serial.println("[Cell] GPRS failed");
    return false;
  }
  Serial.println("[Cell] Connected: " + modem.localIP().toString());

  // Configure SSL context 0
  modem.sendAT("+CSSLCFG=\"sslversion\",0,4"); // TLS 1.2
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
  if (activeConn == CONN_WIFI)
    return WiFi.status() == WL_CONNECTED;
  if (activeConn == CONN_CELL)
    return modem.isGprsConnected();
  return false;
}

void connectNetwork()
{
  if (!tryWifi())
  {
    Serial.println("[Net] Falling back to cellular...");
    if (!tryCell())
    {
      Serial.println("[Net] All connections failed, will retry in loop");
    }
  }
}

// ===== MQTT =====

bool isMqttConnected()
{
  if (activeConn == CONN_WIFI)
    return mqtt.connected();
  if (activeConn == CONN_CELL)
    return modem.mqtt_connected();
  return false;
}

bool mqttPublish(const String &topic, const char *payload)
{
  if (activeConn == CONN_WIFI)
    return mqtt.publish(topic.c_str(), payload);
  if (activeConn == CONN_CELL)
    return modem.mqtt_publish(0, topic.c_str(), payload);
  return false;
}

void mqttConnect()
{
  static unsigned long lastAttempt = 0;
  if (millis() - lastAttempt < 5000)
    return;
  lastAttempt = millis();

  if (!isNetworkUp())
  {
    Serial.println("[Net] Connection dropped, reconnecting...");
    activeConn = CONN_NONE;
    connectNetwork();
    if (activeConn == CONN_NONE)
      return;
  }

  Serial.printf("[MQTT] Connecting via %s...\n", activeConn == CONN_WIFI ? "WiFi" : "Cell");

  if (activeConn == CONN_WIFI)
  {
    mqtt.setServer(mqtt_broker.c_str(), 8883);
    if (mqtt.connect(device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str()))
    {
      Serial.println("[MQTT] WiFi connected");
      mqtt.subscribe(topicSubscribe.c_str());
      forcePublish = true;
    }
    else
    {
      Serial.printf("[MQTT] WiFi failed rc=%d\n", mqtt.state());
    }
  }
  else
  {
    if (modem.mqtt_connect(0, mqtt_broker.c_str(), 8883,
                           device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str()))
    {
      Serial.println("[MQTT] Cell connected");
      modem.mqtt_set_callback(cellMqttCallback);
      modem.mqtt_subscribe(0, topicSubscribe.c_str());
      forcePublish = true;
    }
    else
    {
      Serial.println("[MQTT] Cell failed");
    }
  }
}

// ===== Serial provisioning =====

void handleSerialProvisioning()
{
  if (!Serial.available())
    return;
  String input = Serial.readStringUntil('\n');
  input.trim();
  bool needsMqttReconnect = false;

  if (input.startsWith("SET_USER:"))
  {
    mqtt_user = input.substring(9);
    setPreference("mqtt-config", "user", mqtt_user);
    needsMqttReconnect = true;
    Serial.println("Success: User saved: " + mqtt_user);
  }
  else if (input.startsWith("SET_PASS:"))
  {
    mqtt_pass = input.substring(9);
    setPreference("mqtt-config", "pass", mqtt_pass);
    needsMqttReconnect = true;
    Serial.println("Success: Password saved.");
  }
  else if (input.startsWith("SET_ID:"))
  {
    device_id = input.substring(7);
    setPreference("mqtt-config", "dev_id", device_id);
    updateMqttTopics();
    needsMqttReconnect = true;
    Serial.println("Success: Device ID saved: " + device_id);
  }
  else if (input.startsWith("SET_BROKER:"))
  {
    mqtt_broker = input.substring(11);
    setPreference("mqtt-config", "broker", mqtt_broker);
    needsMqttReconnect = true;
    Serial.println("Success: Broker saved: " + mqtt_broker);
  }
  else if (input.startsWith("SET_SSID:"))
  {
    wifi_ssid = input.substring(9);
    setPreference("wifi-config", "ssid", wifi_ssid);
    Serial.println("Success: SSID saved: " + wifi_ssid);
  }
  else if (input.startsWith("SET_WPASS:"))
  {
    wifi_pass = input.substring(10);
    setPreference("wifi-config", "pass", wifi_pass);
    Serial.println("Success: WiFi password saved.");
  }
  else if (input == "FORCE_PUBLISH")
  {
    forcePublish = true;
    Serial.println("Success: Next GPS update will be published regardless of HDOP/distance.");
  }
  else if (input == "SHOW_CONFIG")
  {
    Serial.println("ID: " + device_id);
    Serial.println("User: " + mqtt_user);
    Serial.println("Broker: " + mqtt_broker);
    Serial.println("WiFi SSID: " + wifi_ssid);
    Serial.printf("Connection: %s\n",
                  activeConn == CONN_WIFI ? "WiFi" : activeConn == CONN_CELL ? "Cell"
                                                                             : "None");
  }
  else if (input == "RESTART")
  {
    Serial.println("Restarting...");
    delay(1000);
    ESP.restart();
  }

  if (needsMqttReconnect)
  {
    Serial.println("[MQTT] Config changed, reconnecting...");
    if (activeConn == CONN_WIFI)
      mqtt.disconnect();
    else if (activeConn == CONN_CELL)
      modem.mqtt_disconnect();
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

  pinMode(BOARD_LED_PIN, OUTPUT);
  digitalWrite(BOARD_LED_PIN, LED_OFF);
  pinMode(MODEM_DTR_PIN, OUTPUT);
  digitalWrite(MODEM_DTR_PIN, LOW);
  pinMode(BOARD_PWRKEY_PIN, OUTPUT);

  bool coldBoot = (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_UNDEFINED);

  if (coldBoot)
  {
    Serial.println("[Boot] Cold boot");

    if (device_id == "G-S3-GENERIC" || mqtt_broker == "mqtt_broker")
      blinkError(5);

    // Full modem power-on sequence (same as before)
    pinMode(MODEM_RESET_PIN, OUTPUT);
    digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);
    delay(100);
    digitalWrite(MODEM_RESET_PIN, MODEM_RESET_LEVEL);
    delay(2600);
    digitalWrite(MODEM_RESET_PIN, !MODEM_RESET_LEVEL);

    digitalWrite(BOARD_PWRKEY_PIN, LOW);
    delay(100);
    digitalWrite(BOARD_PWRKEY_PIN, HIGH);
    delay(MODEM_POWERON_PULSE_WIDTH_MS);
    digitalWrite(BOARD_PWRKEY_PIN, LOW);

    SerialAT.begin(115200, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
    Serial.println("Starting modem...");
    delay(3000);

    int retry = 0;
    while (!modem.testAT(1000))
    {
      Serial.print(".");
      if (retry++ > 30)
      {
        digitalWrite(BOARD_PWRKEY_PIN, HIGH);
        delay(MODEM_POWERON_PULSE_WIDTH_MS);
        digitalWrite(BOARD_PWRKEY_PIN, LOW);
        retry = 0;
      }
    }

    String modemName;
    while ((modemName = modem.getModemName()) == "UNKNOWN")
    {
      Serial.println("Waiting for modem...");
      delay(1000);
    }
    Serial.println("Modem: " + modemName);

    uploadCellCerts();
    connectNetwork();
    rtc_conn_mode = (int)activeConn; // save for next wake

    mqtt.setCallback(wifiMqttCallback);
    mqtt.setKeepAlive(300); // raised from 60 — keeps WiFi MQTT alive across short sleeps
    mqtt.setSocketTimeout(15);
  }
  else
  {
    Serial.println("[Boot] Wake from deep sleep");

    // Account for elapsed time while asleep
    rtc_secs_since_pub += rtc_last_sleep_s;

    // Restore working state from RTC shadow
    activeConn = (ConnMode)rtc_conn_mode;
    last_lat = rtc_last_lat;
    last_lng = rtc_last_lng;
    is_first_fix = rtc_is_first_fix;
    forcePublish = rtc_force_publish;

    SerialAT.begin(115200, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
    delay(500);

    // Sanity-check: modem should still be responsive
    if (!modem.testAT(5000))
    {
      Serial.println("[Boot] Modem not responding after sleep — cold restarting");
      rtc_conn_mode = (int)CONN_NONE;
      ESP.restart();
    }

    // Re-establish network/MQTT only if dropped during sleep
    if (activeConn == CONN_CELL)
    {
      if (!modem.isGprsConnected())
      {
        Serial.println("[Boot] GPRS dropped, reconnecting...");
        modem.gprsConnect(CELLULAR_APN, "", "");
        modem.mqtt_begin(true);
      }
      if (!modem.mqtt_connected())
      {
        Serial.println("[Boot] Cell MQTT dropped, reconnecting...");
        modem.mqtt_connect(0, mqtt_broker.c_str(), 8883,
                           device_id.c_str(), mqtt_user.c_str(), mqtt_pass.c_str());
        modem.mqtt_set_callback(cellMqttCallback);
        modem.mqtt_subscribe(0, topicSubscribe.c_str());
      }
    }
    else
    {
      // WiFi connection dropped during sleep — reconnect everything
      activeConn = CONN_NONE;
      connectNetwork();
      rtc_conn_mode = (int)activeConn;
      mqtt.setCallback(wifiMqttCallback);
      mqtt.setKeepAlive(300);
      mqtt.setSocketTimeout(15);
      if (!isMqttConnected())
        mqttConnect();
    }
  }

  // Enable GPS on every boot before entering loop (cold or warm)
  // Hot fix after re-enable typically takes 5–15 s
  Serial.println("Enabling GPS...");
  while (!modem.enableGPS(MODEM_GPS_ENABLE_GPIO, MODEM_GPS_ENABLE_LEVEL))
    delay(500);
  modem.setGPSBaud(115200);
  Serial.println("GPS enabled");
}

// ===== Loop =====

void loop()
{
  esp_task_wdt_reset();
  handleSerialProvisioning();

  // Service MQTT incoming messages
  if (activeConn == CONN_WIFI)
    mqtt.loop();
  if (activeConn == CONN_CELL)
    modem.mqtt_handle();
  if (!isMqttConnected())
    mqttConnect();

  // ---- Wait for GPS fix ----
  GNSSInfo update;
  bool fixAcquired = false;
  unsigned long gpsStart = millis();

  while (millis() - gpsStart < GPS_FIX_TIMEOUT_MS)
  {
    esp_task_wdt_reset();
    String rawData = modem.getGPSraw();
    update = extractGPS(rawData);

    if (update.hasFix)
    {
      fixAcquired = true;
      break;
    }

    digitalWrite(BOARD_LED_PIN, ledToggle ? LED_OFF : LED_ON);
    ledToggle = !ledToggle;
    Serial.println("[GPS] Waiting for fix...");
    delay(1000);
  }

  // ---- Decide and publish ----
  uint32_t sleepSeconds = SLEEP_STATIC_S;

  if (fixAcquired)
  {
    digitalWrite(BOARD_LED_PIN, LED_ON);

    double distance = is_first_fix ? 0.0 : haversine(last_lat, last_lng, update.latitude, update.longitude);
    bool moving = !is_first_fix && distance > 5.0;
    bool timeForced = (rtc_secs_since_pub >= PUBLISH_INTERVAL_S);
    bool shouldPublish = (update.hdop <= 5.0 && (moving || is_first_fix)) || timeForced || forcePublish;

    float batteryVoltage = readBatVoltage();

    if (shouldPublish)
    {
      JsonDocument doc;
      doc["lat"] = update.latitude;
      doc["lng"] = update.longitude;
      doc["spd"] = update.speed;
      doc["hdop"] = update.hdop;
      doc["sats"] = update.satsUsed;
      doc["dist"] = distance;
      doc["bat"] = batteryVoltage;
      doc["bat_pct"] = getBatteryPercentage(batteryVoltage);

      char buffer[256];
      serializeJson(doc, buffer);

      if (mqttPublish(topicPublish, buffer))
        Serial.println("[MQTT] Published: " + String(buffer));
      else
        Serial.println("[MQTT] Publish failed");

      // Commit to RTC memory
      rtc_last_lat = update.latitude;
      rtc_last_lng = update.longitude;
      rtc_is_first_fix = false;
      rtc_secs_since_pub = 0;
      rtc_static_streak = 0;
      rtc_force_publish = false;

      // Keep working copies in sync
      last_lat = rtc_last_lat;
      last_lng = rtc_last_lng;
      is_first_fix = false;
      forcePublish = false;
    }
    else
    {
      rtc_static_streak++;
      Serial.printf("[GPS] Static (streak %d), skipping\n", rtc_static_streak);
    }

    // ---- Dynamic sleep duration ----
    if (moving)
    {
      sleepSeconds = SLEEP_MOVING_S;
      rtc_static_streak = 0;
    }
    else if (rtc_static_streak >= STATIC_STREAK_LONG)
    {
      sleepSeconds = SLEEP_STATIC_LONG_S;
    }
    else
    {
      sleepSeconds = SLEEP_STATIC_S;
    }
  }
  else
  {
    Serial.println("[GPS] No fix acquired, sleeping anyway");
  }

  digitalWrite(BOARD_LED_PIN, LED_OFF);
  goToSleep(sleepSeconds);
}