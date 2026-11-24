/*
 * ClimaSense — firmware do ESP32 (envia leituras para a API a cada INTERVAL).
 *
 * Bibliotecas (Gerenciador de Bibliotecas da Arduino IDE / PlatformIO):
 *   - DHT sensor library (Adafruit) + Adafruit Unified Sensor
 *   - Adafruit BMP280 Library
 *   - ArduinoJson 7.x  (usa JsonDocument; NÃO funciona com a 6.x)
 *
 * Ligações (ESP32 DevKit):
 *   DHT22   DATA -> GPIO4            (resistor pull-up de 10 kΩ entre DATA e 3V3, se o módulo não tiver)
 *   BMP280  SDA  -> GPIO21,  SCL -> GPIO22   (I2C, endereço 0x76 ou 0x77)
 *   MQ-135  AO   -> GPIO34           (ADC1; atenção: a saída do módulo pode chegar a 5 V, use divisor de tensão para 3,3 V)
 *   LDR     divisor de tensão (LDR + resistor 10 kΩ) -> GPIO35 (ADC1)
 *
 * CORREÇÃO em relação à versão anterior: o LDR estava no GPIO19, que NÃO tem conversor analógico no ESP32
 * (analogRead não funciona ali). Use um pino do ADC1: 32, 33, 34, 35, 36 ou 39. Evite os pinos do ADC2
 * (0, 2, 4, 12–15, 25–27) para leitura analógica, pois o ADC2 deixa de funcionar quando o Wi-Fi está ligado.
 *
 * Contrato com a API (POST /api/readings, cabeçalho X-API-Key): ver /docs no servidor.
 * Sensor com falha NÃO envia valores e é listado em "sensor_errors" (o painel mostra "Sem leitura").
 * O timestamp é omitido de propósito: o servidor usa a própria hora (UTC) e evita duplicatas.
 */
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>

// ---------------- Configuração (EDITE) ----------------
#define DHT_PIN    4
#define DHT_TYPE   DHT22
#define MQ135_PIN  34   // ADC1_CH6 (somente entrada)
#define LDR_PIN    35   // ADC1_CH7 (antes: 19, que não lê analógico)

const char* WIFI_SSID     = "SEU_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA";

// Local (teste no PC):  "http://192.168.0.10:8000/api/readings"  (IP do computador que roda o uvicorn)
// Nuvem:                "https://SEU-SERVIDOR.onrender.com/api/readings"
const char* API_URL = "http://192.168.0.10:8000/api/readings";
const char* API_KEY = "COLE_AQUI_A_STATION_API_KEY";   // mesma STATION_API_KEY do .env do servidor
const char* STATION_ID = "estacao_01";                   // mesmo STATION_ID do .env

const unsigned long INTERVAL_MS     = 60000;   // intervalo entre envios
const unsigned long WIFI_TIMEOUT_MS = 20000;
const int           HTTP_TIMEOUT_MS = 30000;   // servidores gratuitos podem demorar a "acordar"
// ------------------------------------------------------

DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_BMP280 bmp;
WiFiClientSecure secureClient;
bool bmpOk = false;
unsigned long lastSend = 0;
bool firstRun = true;

bool connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("Conectando ao Wi-Fi \"%s\"", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi conectado. IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }
  Serial.println("Falha ao conectar no Wi-Fi.");
  return false;
}

void sendReading() {
  if (!connectWifi()) return;

  // --- leituras ---
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  bool dhtOk = !isnan(t) && !isnan(h) && t >= -40 && t <= 80 && h >= 0 && h <= 100;

  float pressure = NAN, bmpTemp = NAN;
  bool bmpValid = false;
  if (bmpOk) {
    bmpTemp = bmp.readTemperature();
    pressure = bmp.readPressure() / 100.0f;  // Pa -> hPa
    bmpValid = !isnan(bmpTemp) && !isnan(pressure) && pressure >= 300 && pressure <= 1100 && bmpTemp >= -40 && bmpTemp <= 85;
  }

  int mq135 = analogRead(MQ135_PIN);  // 0..4095 (bruto, sem calibração)
  int ldr   = analogRead(LDR_PIN);    // 0..4095 (relativo, não é lux)

  // --- JSON ---
  JsonDocument doc;
  doc["station_id"] = STATION_ID;
  doc["source"] = "hardware";
  JsonArray errors = doc["sensor_errors"].to<JsonArray>();

  if (dhtOk) {
    doc["temperature_c"] = roundf(t * 10) / 10;
    doc["humidity_pct"] = roundf(h * 10) / 10;
  } else {
    errors.add("dht22");
  }
  if (bmpValid) {
    doc["pressure_hpa"] = roundf(pressure * 10) / 10;
    doc["bmp280_temperature_c"] = roundf(bmpTemp * 10) / 10;
  } else {
    errors.add("bmp280");
  }
  doc["mq135_raw"] = mq135;
  doc["ldr_raw"] = ldr;

  String body;
  serializeJson(doc, body);
  Serial.println("Enviando: " + body);

  // --- HTTP POST ---
  HTTPClient http;
  bool https = String(API_URL).startsWith("https://");
  bool began;
  if (https) {
    secureClient.setInsecure();  // sem validar certificado (projeto acadêmico). Em produção use setCACert().
    began = http.begin(secureClient, API_URL);
  } else {
    began = http.begin(API_URL);
  }
  if (!began) {
    Serial.println("URL da API inválida.");
    return;
  }
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);

  int code = http.POST(body);
  if (code > 0) {
    Serial.printf("Resposta HTTP %d\n", code);
    if (code == 201) Serial.println("OK: leitura gravada.");
    else if (code == 200) Serial.println("OK: leitura já existia (reenvio).");
    else if (code == 401) Serial.println("ERRO: chave de API ausente/errada (confira API_KEY).");
    else if (code == 503) Serial.println("ERRO: STATION_API_KEY não configurada no servidor.");
    else if (code == 404) Serial.println("ERRO: STATION_ID não cadastrado no servidor.");
    else if (code == 422) Serial.println("ERRO: dados inválidos (veja o detalhe abaixo).");
    if (code >= 400) Serial.println(http.getString());
  } else {
    Serial.printf("Falha na conexão com a API: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nClimaSense — iniciando...");

  analogReadResolution(12);                 // 0..4095
  analogSetPinAttenuation(MQ135_PIN, ADC_11db);  // faixa até ~3,3 V
  analogSetPinAttenuation(LDR_PIN, ADC_11db);

  dht.begin();
  Wire.begin();                             // SDA=21, SCL=22
  bmpOk = bmp.begin(0x76) || bmp.begin(0x77);
  Serial.println(bmpOk ? "BMP280 encontrado." : "BMP280 NÃO encontrado (será enviado como falha).");

  connectWifi();
}

void loop() {
  if (firstRun || millis() - lastSend >= INTERVAL_MS) {
    firstRun = false;
    lastSend = millis();
    sendReading();
  }
  delay(50);
}
