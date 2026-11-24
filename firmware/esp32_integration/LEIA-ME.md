# Firmware ESP32

1. Instale as bibliotecas listadas no cabeçalho do `esp32_integration.ino` (ArduinoJson **7.x**).
2. Edite `WIFI_SSID`, `WIFI_PASSWORD`, `API_URL`, `API_KEY` e `STATION_ID`.
   - `API_KEY` = valor de `STATION_API_KEY` do `.env` do servidor.
   - Teste local: use o IP do seu PC (`ipconfig` no Windows), ex.: `http://192.168.0.10:8000/api/readings`,
     e inicie o servidor com `uvicorn app.main:app --host 0.0.0.0 --port 8000` (para aceitar conexões da rede).
     O ESP32 e o PC precisam estar na mesma rede Wi-Fi (e o firewall do Windows pode pedir liberação da porta 8000).
3. Selecione a placa "ESP32 Dev Module", abra o Monitor Serial a 115200 e envie.
4. Resposta esperada no Monitor Serial: `Resposta HTTP 201` e `OK: leitura gravada.`

> Este código não foi compilado no ambiente em que foi escrito: compile e teste na sua placa. Se aparecer erro de
> biblioteca, confira as versões (principalmente ArduinoJson 7).
