/*
  Projeto ESP8266 + Django: Sistema de Controle e Monitoramento
  Este script permite que um ESP8266 se comunique com uma aplicação web Django,
  enviando dados de sensores (temperatura/umidade) e recebendo comandos para
  controlar dispositivos (relés, transmissor IR, buzzer).

  Funcionalidades principais:
  1. Conexão com rede Wi-Fi.
  2. Leitura de sensores DHT11.
  3. Envio de dados de telemetria (temperatura, umidade, estado de relé)
     para o servidor Django.
  4. Verificação periódica de comandos pendentes no servidor Django.
  5. Execução de comandos recebidos, como:
     - Acionamento de relés.
     - Envio de sinais infravermelho (IR) para ar-condicionado.
     - Reprodução de melodias em um buzzer.
  6. Detecção de pressionamento de botões físicos para controle local.
  7. Confirmação da execução dos comandos local para o servidor.
  8. Uso de timers (millis()) para evitar a função delay() e manter a
     execução não bloqueante, permitindo que o ESP realize várias tarefas
     "simultaneamente".
*/

// --- BIBLIOTECAS ---
// Gerenciamento de Wi-Fi e requisições HTTP
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>

// Processamento de dados JSON para comunicação com a API
#include <ArduinoJson.h>

// Sensores e periféricos
#include <DHT.h> // Sensor de temperatura e umidade
#include <IRremoteESP8266.h> // Transmissor infravermelho
#include <IRsend.h> // Parte da biblioteca IRremoteESP8266 para enviar sinais
#include "pitches.h" // Arquivo com as frequências das notas musicais para o buzzer
// Arquivo com credenciais de rede e tokens
#include "password_ssid.h" 


// --- DEFINIÇÕES DE PINOS (GPIOs do ESP8266) ---
// Use definições #define para facilitar a mudança de pinos no futuro.
// A nomenclatura `D1`, `D2`, etc., para os pinos GPIO reais.
#define D0 16
#define D1 5
#define D2 4
#define D3 0
#define D4 2
#define D5 14
#define D6 12
#define D7 13
#define D8 15
#define S3 10

// Atribuição de pinos a periféricos específicos
#define BUZZER_PIN D1       // Pino para o Buzzer
#define IR_SEND_PIN D2      // Pino para o transmissor IR
#define BTN_LIGAR_PIN D5    // Pino do botão Ligar
#define BTN_DESLIGAR_PIN D6 // Pino do botão Desligar
#define BTN_VENTILACAO_PIN D7 // Pino do botão Ventilação
#define DHT_PIN D3          // Pino para o sensor DHT

// Configuração do tipo de sensor DHT
#define DHT_TYPE DHT11      // Use DHT11 ou DHT22 conforme o sensor  

// --- VARIÁVEIS E CONSTANTES GLOBAIS ---
// Configurações de Rede e Servidor Django
const char* ssid = txtssidE;
const char* password = txtpasswordE;
const char* djangoTelemetryUrl = txtdjangoTelemetryUrl; // URL da API do Django para POST
const char* djangoDeviceUrl = txtdjangoDeviceUrl;       // URL da API do Django para GET/PUT
const char* AUTH_TOKEN = txtToken;     // Token de autenticação da API 
const char* DEVICE_ID = txtDEVICE_ID; // ID único deste dispositivo 

// Inicialização dos objetos de hardware
DHT dht(DHT_PIN, DHT_TYPE);
IRsend irsend(IR_SEND_PIN);

// Estrutura para representar o estado de um relé
struct Relay {
    int pin;
    bool state;
};
Relay rele1 = {S3, LOW}; // Inicializa o relé 1 no pino S3 com estado LOW (desligado)

// Variáveis de estado e sensores
int temperature = 0;
int humidity = 0;

// Variáveis de rastreamento de AÇÕES
// lastButtonAction armazena a última ação local do usuário (botão físico)
String lastButtonAction = "Nenhum"; 
// lastExecutedAction armazena a última ação executada remotamente (Django/Celery)
String lastExecutedAction = "Nenhum";
// lastExecutedTarget armazena o alvo da última ação executada remotamente
String lastExecutedTarget = "Nenhum";

// Variáveis para controle de tempo (timers)
// O uso de `unsigned long` e `millis()` evita a paralisação do código com `delay()`.
unsigned long lastSendMillis = 0;
const unsigned long sendInterval = 60000; // Intervalo para enviar dados (60 segundos ou 10 minutos (600000) para produção)
unsigned long lastCheckCommandMillis = 0;
const unsigned long checkCommandInterval = 10000; // Intervalo para checar comandos (10 segundos)
unsigned long lastLedMillis = 0;
const unsigned long ledInterval = 500; // Intervalo para piscar o LED (0.5 segundos) 

// Variáveis (flag) de controle de estado para envio de dados
bool shouldSendDataNow = LOW;

// Variáveis de flag para interrupção (volatile pois são modificadas em ISRs)
volatile bool btnLigarPressed = LOW;
volatile bool btnDesligarPressed = LOW;
volatile bool btnVentilacaoPressed = LOW;

// Variável para controlar o tempo da última ação de botão (debounce de software)
unsigned long lastButtonActionMillis = 0;
const unsigned long minActionInterval = 200; // Intervalo mínimo entre ações (200 ms)

// --- ISRS (Interrupção de Serviço de Rotina) ---
void IRAM_ATTR handleBtnLigar() {
  if (digitalRead(BTN_LIGAR_PIN) == LOW) {
    btnLigarPressed = true;
  }
}

void IRAM_ATTR handleBtnDesligar() {
  if (digitalRead(BTN_DESLIGAR_PIN) == LOW) {
    btnDesligarPressed = true;
  }
}

void IRAM_ATTR handleBtnVentilacao() {
  if (digitalRead(BTN_VENTILACAO_PIN) == LOW) {
    btnVentilacaoPressed = true;
  }
}


// --- DADOS DE COMANDOS IR (RAW DATA) ---
// Estes arrays contêm os códigos RAW capturados do controle do ar-condicionado.
// Mantenha-os aqui para facilitar a visualização e a edição.
uint16_t rawDataLigar[349] = {742, 17772, 3270, 8748, 740, 254, 756, 1240, 760, 238, 760, 240, 756, 240, 760, 240, 758, 238, 760, 236, 762, 242, 754, 1242, 756, 240, 756, 240, 758, 1268, 734, 264, 634, 366, 718, 1278, 740, 1258, 756, 1240, 750, 1248, 746, 1250, 746, 254, 732, 276, 720, 268, 726, 278, 712, 286, 698, 302, 668, 360, 634, 376, 620, 380, 588, 420, 572, 434, 562, 436, 558, 442, 550, 448, 544, 456, 536, 462, 530, 470, 520, 480, 512, 486, 506, 492, 500, 498, 496, 504, 494, 522, 476, 528, 470, 530, 470, 528, 484, 514, 494, 504, 494, 504, 494, 504, 496, 502, 492, 506, 490, 1506, 492, 1506, 496, 1500, 494, 1502, 498, 3014, 2978, 9010, 496, 1526, 470, 528, 468, 530, 490, 508, 494, 504, 498, 500, 498, 500, 494, 504, 498, 500, 498, 1498, 496, 502, 494, 504, 496, 1502, 494, 502, 494, 1504, 496, 1526, 470, 1528, 468, 1530, 494, 1504, 498, 1498, 496, 504, 498, 500, 494, 504, 494, 502, 496, 502, 494, 504, 496, 500, 494, 504, 496, 506, 496, 514, 480, 526, 472, 530, 466, 532, 470, 528, 494, 504, 498, 500, 498, 500, 496, 502, 496, 502, 494, 506, 498, 500, 500, 498, 498, 500, 496, 502, 498, 500, 498, 500, 500, 498, 498, 512, 484, 524, 474, 528, 472, 526, 472, 526, 494, 504, 496, 502, 500, 498, 498, 500, 496, 3010, 2982, 9010, 494, 1500, 498, 500, 500, 498, 496, 502, 496, 502, 496, 500, 498, 502, 496, 516, 478, 528, 472, 1530, 490, 506, 496, 504, 498, 1498, 496, 500, 496, 1502, 496, 1500, 496, 502, 494, 1504, 496, 1500, 496, 1502, 496, 1522, 474, 1528, 470, 528, 496, 1502, 496, 1500, 496, 502, 496, 502, 496, 502, 496, 1500, 496, 1500, 498, 1500, 496, 502, 496, 502, 496, 522, 476, 524, 474, 528, 470, 528, 488, 510, 496, 1502, 500, 496, 498, 1500, 496, 1502, 496, 500, 496, 1502, 496, 1500, 494, 502, 498, 500, 496, 504, 498, 514, 484, 524, 472, 530, 468, 530, 490, 1506, 500, 1498, 496, 1502, 496, 1500, 498}; 
uint16_t rawDataDesligar[349] = {830, 17684, 3268, 8748, 750, 246, 756, 1242, 758, 242, 756, 240, 758, 242, 758, 242, 756, 238, 760, 240, 758, 242, 754, 1244, 754, 240, 756, 240, 754, 1276, 712, 1282, 726, 270, 732, 1268, 754, 1242, 752, 1246, 750, 1248, 742, 1254, 736, 266, 730, 266, 728, 274, 718, 276, 720, 278, 690, 334, 646, 368, 632, 372, 622, 378, 584, 428, 566, 436, 558, 442, 550, 450, 542, 456, 534, 466, 526, 472, 518, 480, 514, 486, 504, 494, 500, 498, 494, 510, 488, 524, 472, 530, 470, 532, 470, 528, 488, 510, 492, 504, 492, 508, 494, 504, 494, 504, 494, 504, 492, 506, 494, 504, 496, 502, 496, 502, 492, 1506, 490, 1506, 494, 3014, 2982, 9006, 494, 1524, 472, 530, 472, 526, 492, 506, 494, 504, 500, 498, 496, 502, 496, 502, 498, 502, 496, 1502, 496, 502, 494, 502, 496, 1500, 496, 504, 494, 1510, 490, 1522, 474, 1526, 468, 1530, 496, 1502, 498, 1500, 496, 502, 498, 500, 494, 504, 494, 504, 494, 504, 496, 502, 498, 500, 496, 502, 496, 514, 484, 524, 474, 524, 474, 528, 470, 528, 496, 504, 496, 502, 498, 502, 496, 500, 498, 500, 498, 500, 500, 500, 498, 500, 496, 502, 494, 504, 496, 502, 496, 512, 488, 522, 472, 528, 470, 530, 468, 530, 496, 502, 496, 502, 496, 500, 498, 502, 498, 3004, 2986, 9006, 498, 1498, 498, 500, 498, 500, 496, 502, 494, 504, 494, 504, 496, 512, 488, 518, 474, 528, 474, 1526, 488, 510, 496, 502, 496, 1502, 496, 1502, 494, 1502, 496, 1502, 496, 502, 494, 1504, 496, 1500, 496, 1502, 496, 1522, 474, 1528, 468, 528, 494, 1502, 494, 1504, 496, 502, 494, 504, 494, 504, 496, 1502, 494, 1502, 496, 1500, 496, 500, 496, 506, 496, 518, 476, 528, 476, 524, 470, 528, 494, 504, 496, 1500, 498, 500, 496, 1502, 498, 1500, 494, 504, 498, 1500, 496, 1500, 496, 502, 496, 502, 498, 514, 480, 524, 476, 526, 474, 528, 470, 528, 494, 504, 494, 504, 498, 1500, 498, 1500, 496};
uint16_t rawDataVentilacao[233] = {848, 17754, 3272, 8744, 728, 266, 750, 1248, 760, 238, 756, 240, 756, 246, 754, 240, 758, 242, 750, 246, 756, 240, 758, 1244, 752, 246, 752, 248, 748, 1282, 718, 282, 624, 368, 712, 1284, 736, 1258, 754, 1244, 746, 1252, 742, 1260, 730, 264, 732, 280, 714, 280, 712, 288, 708, 278, 704, 302, 668, 364, 628, 378, 616, 384, 586, 418, 576, 434, 562, 438, 556, 442, 550, 448, 544, 454, 536, 462, 530, 468, 520, 480, 514, 486, 504, 494, 500, 500, 496, 506, 492, 522, 476, 522, 470, 534, 466, 532, 464, 532, 492, 506, 494, 504, 492, 506, 494, 504, 494, 504, 494, 1504, 492, 1504, 492, 1504, 496, 1500, 496, 3014, 2978, 9016, 494, 1518, 474, 530, 468, 530, 486, 512, 496, 502, 496, 504, 496, 502, 496, 502, 498, 502, 492, 1506, 496, 502, 498, 502, 494, 1502, 494, 504, 496, 1508, 492, 1518, 476, 528, 470, 1528, 494, 1504, 498, 1498, 498, 1498, 496, 1502, 496, 502, 496, 1500, 500, 1498, 496, 502, 494, 504, 498, 518, 476, 1526, 472, 1528, 484, 1512, 498, 500, 494, 504, 496, 502, 494, 504, 496, 502, 498, 500, 496, 502, 494, 504, 494, 1502, 496, 1502, 500, 504, 492, 522, 474, 1530, 474, 1524, 492, 1506, 496, 502, 500, 500, 494, 502, 498, 500, 494, 504, 498, 500, 496, 1502, 496, 1502, 494, 1502, 496, 1520, 506};

// --- MELODIAS PARA O BUZZER ---
// O formato é {nota, duração}, onde a duração é 1/X da nota inteira.
// Por exemplo: 4 = 1/4 (semínima), 8 = 1/8 (colcheia).
int melody1[] = {
  NOTE_C5, 4, NOTE_G4, 8, NOTE_AS4, 4, NOTE_A4, 8,
  NOTE_G4, 16, NOTE_C4, 8, NOTE_C4, 16, NOTE_G4, 16, NOTE_G4, 8, NOTE_G4, 16,
  NOTE_C5, 4, NOTE_G4, 8, NOTE_AS4, 4, NOTE_A4, 8,
  NOTE_G4, 2,
  
  NOTE_C5, 4, NOTE_G4, 8, NOTE_AS4, 4, NOTE_A4, 8,
  NOTE_G4, 16, NOTE_C4, 8, NOTE_C4, 16, NOTE_G4, 16, NOTE_G4, 8, NOTE_G4, 16,
  NOTE_F4, 8, NOTE_E4, 8, NOTE_D4, 8, NOTE_C4, 8,
  NOTE_C4, 2,

  REST, 1
};

// Melodia 2
int melody2[] = {
  NOTE_B4, 16, NOTE_B5, 16, NOTE_FS5, 16, NOTE_DS5, 16, 
  NOTE_B5, 32, NOTE_FS5, -16, NOTE_DS5, 8, NOTE_C5, 16,
  NOTE_C6, 16, NOTE_G6, 16, NOTE_E6, 16, NOTE_C6, 32, NOTE_G6, -16, NOTE_E6, 8,

  NOTE_B4, 16, NOTE_B5, 16, NOTE_FS5, 16, NOTE_DS5, 16, NOTE_B5, 32, 
  NOTE_FS5, -16, NOTE_DS5, 8, NOTE_DS5, 32, NOTE_E5, 32, NOTE_F5, 32,
  NOTE_F5, 32, NOTE_FS5, 32, NOTE_G5, 32, NOTE_G5, 32, NOTE_GS5, 32, NOTE_A5, 16, NOTE_B5, 8
};

// Melodia 3
int melody3[] = {
  NOTE_B4, 16, NOTE_B5, 16, NOTE_FS5, 16, NOTE_DS5, 16, 
  NOTE_B5, 32, NOTE_FS5, -16, NOTE_DS5, 8, NOTE_C5, 16,
  NOTE_C6, 16, NOTE_G6, 16, NOTE_E6, 16, NOTE_C6, 32, NOTE_G6, -16, NOTE_E6, 8,

  NOTE_B4, 16, NOTE_B5, 16, NOTE_FS5, 16, NOTE_DS5, 16, NOTE_B5, 32, 
  NOTE_FS5, -16, NOTE_DS5, 8, NOTE_DS5, 32, NOTE_E5, 32, NOTE_F5, 32,
  NOTE_F5, 32, NOTE_FS5, 32, NOTE_G5, 32, NOTE_G5, 32, NOTE_GS5, 32, NOTE_A5, 16, NOTE_B5, 8
};

// --- FUNÇÕES DE LÓGICA DO PROGRAMA ---

/**
 * @brief Conecta o ESP8266 à rede Wi-Fi.
 * A função tenta se conectar à rede usando as credenciais definidas.
 * Se a rede for oculta, o parâmetro `true` é usado na WiFi.begin
 */
void connectWiFi() {
  Serial.print("Conectando-se a ");
  Serial.println(ssid);

  WiFi.begin(ssid, password, 0, NULL, true); // Usa `true` para redes ocultas (hidden)

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado!");
  Serial.print("Endereço IP: ");
  Serial.println(WiFi.localIP());
}

/**
 * @brief Adiciona o cabeçalho de autenticação (Token) à requisição HTTP.
 * @param http Objeto HTTPClient por referência.
 */
void addAuthHeader(HTTPClient& http) {
  String authHeader = "Token ";
  authHeader += AUTH_TOKEN;
  http.addHeader("Authorization", authHeader);
}

/**
 * @brief Envia dados de sensores e estado para o servidor Django via requisição POST.
 */
void sendDataToDjango() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    String postUrl = String(djangoTelemetryUrl);
    http.begin(client, postUrl);
    http.addHeader("Content-Type", "application/json");
    addAuthHeader(http);

    StaticJsonDocument<400> doc; // Aumentado para acomodar raw_data, caso necessário

    // Envio os dados básicos (o Django irá atualizar se houver mudança)
    doc["name"] = txtname;
    doc["device_type"] = txtdevice_type;
    doc["location"] = txtnlocation;

    // Dados de Telemetria
    doc["temperature_celsius"] = temperature; 
    doc["humidity_percent"] = humidity;      
    doc["relay_state_D1"] = rele1.state;
    doc["last_button_action"] = lastButtonAction;
    
    // Adicionar dados brutos (Ações locais e remotas)
    JsonObject raw_data_obj = doc.createNestedObject("raw_data");
    raw_data_obj["last_button_action"] = lastButtonAction;
    raw_data_obj["last_executed_action"] = lastExecutedAction;
    raw_data_obj["last_executed_target"] = lastExecutedTarget;

    String jsonString;
    serializeJson(doc, jsonString);

    Serial.print("Enviando dados: ");
    Serial.println(jsonString);

    int httpResponseCode = http.POST(jsonString);

    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code (POST): %d\n", httpResponseCode);
      Serial.println(http.getString());
      // LIMPA AS VARIÁVEIS DE AÇÃO APÓS O ENVIO BEM-SUCEDIDO
      lastButtonAction = "Nenhum";
      lastExecutedAction = "Nenhum";
      lastExecutedTarget = "Nenhum";
    } else {
      Serial.printf("Error code (POST): %d\n", httpResponseCode);
      Serial.printf("HTTP Error (POST): %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  } else {
    Serial.println("Wi-Fi não conectado, não foi possível enviar dados.");
  }
}

/**
 * @brief Envia uma requisição PUT para o servidor confirmando a execução de um comando.
 * A requisição zera o campo `pending_command` no servidor.
 * @param executedCommand Nome do comando executado.
 * @param target Alvo do comando (ex: "rele_D1", "ar-condicionado").
 */
void sendCommandExecutedConfirmation(const char* executedCommand, const char* target) {
    if (WiFi.status() == WL_CONNECTED) {
        WiFiClient client;
        HTTPClient http;

        // ATUALIZA AS VARIÁVEIS GLOBAIS ANTES DE ENVIAR A CONFIRMAÇÃO
        lastExecutedAction = executedCommand; 
        lastExecutedTarget = target;

        // Constrói a URL para PUT, usando o DEVICE_ID
        String putUrl = String(djangoDeviceUrl) + String(DEVICE_ID) + "/";
        http.begin(client, putUrl);
        http.addHeader("Content-Type", "application/json");
        addAuthHeader(http);

        StaticJsonDocument<200> doc;
        doc["last_command"] = executedCommand;
        // Definir `pending_command` como `nullptr` sinaliza ao Django para limpar o comando
        doc["pending_command"] = nullptr; 
        
        String jsonString;
        serializeJson(doc, jsonString);

        Serial.print("Enviando confirmação de comando (PUT): ");
        Serial.println(jsonString);

        int httpResponseCode = http.PUT(jsonString);

        if (httpResponseCode > 0) {
            Serial.printf("HTTP Response code (PUT): %d\n", httpResponseCode);
            Serial.println(http.getString());
        } else {
            Serial.printf("Error code (PUT): %d\n", httpResponseCode);
            Serial.printf("HTTP Error (PUT): %s\n", http.errorToString(httpResponseCode).c_str());
        }
        http.end();
    } else {
        Serial.println("Wi-Fi não conectado, não foi possível enviar confirmação.");
    }
}

/**
 * @brief Realiza uma requisição GET para verificar se há comandos pendentes no servidor Django.
 * Se um comando for encontrado, ele é executado e uma confirmação é enviada.
 */
void receiveCommandsFromDjango() {
  if (WiFi.status() == WL_CONNECTED) {
      WiFiClient client;
      HTTPClient http;

      String getUrl = String(djangoDeviceUrl) + String(DEVICE_ID) + "/";
      http.begin(client, getUrl);
      addAuthHeader(http);
      
      Serial.print("Verificando por comandos em: ");
      Serial.println(getUrl);

      int httpResponseCode = http.GET();

      if (httpResponseCode > 0) {
        String payload = http.getString();

        StaticJsonDocument<400> doc;
        DeserializationError error = deserializeJson(doc, payload);

        if (error) { return; }

        const char* status = doc["status"];

        if (strcmp(status, "command_pending") == 0) {
          Serial.println("COMANDO PENDENTE RECEBIDO!");
          
          if (doc.containsKey("command") && !doc["command"].isNull()) {  
            JsonObject command = doc["command"];
            const char* action = command["action"];
            const char* target = command["target"];
            int value = command["value"] | 0;

            // Lógica para executar o comando
            if (strcmp(action, "ligar_rele") == 0 && strcmp(target, "rele_D1") == 0) {
              rele1.state = HIGH;
              sendCommandExecutedConfirmation("ligar_rele", "rele_D1");
              shouldSendDataNow = HIGH;
            } else if (strcmp(action, "desligar_rele") == 0 && strcmp(target, "rele_D1") == 0) {
              rele1.state = LOW;
              sendCommandExecutedConfirmation("desligar_rele", "rele_D1");
              shouldSendDataNow = HIGH;
            } else if (strcmp(action, "ligar_ar") == 0 && strcmp(target, "ar-condicionado") == 0) {
              sendIrCommand(rawDataLigar, 349);
              sendCommandExecutedConfirmation("ligar_ar", "ar-condicionado");
              shouldSendDataNow = HIGH;
            } else if (strcmp(action, "ventilacao_ar") == 0 && strcmp(target, "ar-condicionado") == 0) {
              sendIrCommand(rawDataVentilacao, 233);
              sendCommandExecutedConfirmation("ventilacao_ar", "ar-condicionado");
              shouldSendDataNow = HIGH;
            } else if (strcmp(action, "musica") == 0 && strcmp(target, "buzzer") == 0) {
              if (value == 1) {
                int numNotes = sizeof(melody1) / sizeof(melody1[0]);
                tocarMelodia(melody1, numNotes);
                sendCommandExecutedConfirmation("musica_1", "buzzer");
                shouldSendDataNow = HIGH;
              } else if (value == 2) {
                int numNotes = sizeof(melody2) / sizeof(melody2[0]);
                tocarMelodia(melody2, numNotes);
                sendCommandExecutedConfirmation("musica_2", "buzzer");
                shouldSendDataNow = HIGH;
              } else if (value == 3) {
                int numNotes = sizeof(melody3) / sizeof(melody3[0]);
                tocarMelodia(melody3, numNotes);
                sendCommandExecutedConfirmation("musica_3", "buzzer");
                shouldSendDataNow = HIGH;
              } else {
                sendCommandExecutedConfirmation("musica_invalida", "buzzer");
              }
            } 
            updateSaida(); 
          } 
        } 
      }
      http.end();
  }
}

/**
 * @brief Configura os pinos de entrada e saída (GPIOs) do ESP8266.
 */
void conf_GPIO_init() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  pinMode(rele1.pin, OUTPUT);
  digitalWrite(rele1.pin, rele1.state);
  pinMode(BTN_LIGAR_PIN, INPUT_PULLUP);
  pinMode(BTN_DESLIGAR_PIN, INPUT_PULLUP);
  pinMode(BTN_VENTILACAO_PIN, INPUT_PULLUP);  

  // CONFIGURAÇÃO DAS INTERRUPÇÕES - FALLING para disparar quando o pino vai de HIGH (solto) para LOW (pressionado)
  attachInterrupt(digitalPinToInterrupt(BTN_LIGAR_PIN), handleBtnLigar, FALLING);
  attachInterrupt(digitalPinToInterrupt(BTN_DESLIGAR_PIN), handleBtnDesligar, FALLING);
  attachInterrupt(digitalPinToInterrupt(BTN_VENTILACAO_PIN), handleBtnVentilacao, FALLING);
}

/**
 * @brief Atualiza o estado dos pinos de saída (relés, etc.) com base nas variáveis de estado.
 */
void updateSaida() {
  digitalWrite(rele1.pin, rele1.state);
}

/**
 * @brief Pisca o LED de status do ESP8266.
 */
void piscaLed() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); 
}

/**
 * @brief Realiza a leitura do sensor DHT (temperatura e umidade).
 */
void readSensor() {
  float newHumidity = dht.readHumidity();
  float newTemperature = dht.readTemperature();

  if (isnan(newHumidity) || isnan(newTemperature)) {
    Serial.println("Erro ao ler o sensor DHT!");
  } else {
    temperature = (int)newTemperature;
    humidity = (int)newHumidity;
  }
}

/**
 * @brief Envia um comando IR a partir de um array de dados brutos.
 * @param rawData O array de dados brutos do comando IR.
 * @param length O tamanho do array.
 */
void sendIrCommand(const uint16_t rawData[], uint16_t length) {
  irsend.sendRaw(rawData, length, 38);
  delay(10);
}

/**
 * @brief Processa as ações dos botões disparadas pelas interrupções (ISR).
 * Garante que a ação só ocorra uma vez por pressionamento e com debounce de ação.
 */
void checkButtons() {
    unsigned long currentMillis = millis();
    
    // --- Lógica para o Botão Ligar RELE ---
    if (btnLigarPressed) {
      if (currentMillis - lastButtonActionMillis >= minActionInterval) {
          tone(BUZZER_PIN, 800, 100);        
          rele1.state = HIGH; 
          lastButtonAction = "Botao Ligar RELE"; // Ação local
          shouldSendDataNow = true;
          //lastButtonActionMillis = currentMillis;
          lastButtonActionMillis = millis();
      }
      btnLigarPressed = LOW; 
    }

    // --- Lógica para o Botão Desligar RELE ---
    if (btnDesligarPressed) {
      if (currentMillis - lastButtonActionMillis >= minActionInterval) {
          tone(BUZZER_PIN, 800, 100); 
          rele1.state = LOW; 
          lastButtonAction = "Botao Desligar RELE"; // Ação local
          shouldSendDataNow = true;
          //lastButtonActionMillis = currentMillis;
          lastButtonActionMillis = millis();
      }
      btnDesligarPressed = LOW; 
    }

    // --- Lógica para o Botão Ventilacao AR ---
    if (btnVentilacaoPressed) {
      if (currentMillis - lastButtonActionMillis >= minActionInterval) {
          tone(BUZZER_PIN, 800, 100);       
          sendIrCommand(rawDataVentilacao, 233);
          lastButtonAction = "Botao Ventilacao AR"; // Ação local
          shouldSendDataNow = true;
          //lastButtonActionMillis = currentMillis;
          lastButtonActionMillis = millis();
      }
      btnVentilacaoPressed = LOW; 
    }
}

/**
 * @brief Toca uma melodia no buzzer com base em um array de notas e durações.
 * @param melody_and_durations Array com as notas e suas durações.
 * @param arraySize O tamanho total do array.
 */
void tocarMelodia(int melody_and_durations[], int arraySize) {
  int tempo = 100; // Tempo base
  int wholeNoteDuration = (60000 * 4) / tempo;
  int numNotes = arraySize / 2;

  for (int thisNote = 0; thisNote < numNotes * 2; thisNote += 2) {
    int note = melody_and_durations[thisNote];
    int divider = melody_and_durations[thisNote + 1];
    int noteDuration;

    if (divider > 0) {
      noteDuration = wholeNoteDuration / divider;
    } else if (divider < 0) {
      noteDuration = (wholeNoteDuration / abs(divider)) * 1.5;
    } else {
      noteDuration = 0;
    }

    if (note != REST) {
      tone(BUZZER_PIN, note, noteDuration * 0.9);
    }

    delay(noteDuration);
    noTone(BUZZER_PIN);
  }
}

// --- FUNÇÕES PRINCIPAIS DA IDE DO ARDUINO ---

/**
 * @brief Função de inicialização, executada uma única vez ao ligar ou resetar.
 */
void setup() {
  Serial.begin(115200);
  delay(10);
  connectWiFi();
  sendDataToDjango(); // Primeiro envio para registrar o IP e o Device no Django

  conf_GPIO_init();
  dht.begin();
  irsend.begin();
}

/**
 * @brief Função de loop, executada repetidamente após a função setup.
 * Contém a lógica principal do programa, gerenciada por "timers-millis" para não bloquear
 * a execução.
 */
void loop() {
  // Lógica de tempo
  unsigned long currentMillis = millis();

  // Verifica os botões a cada loop
  checkButtons();

  // Garante que a saída (relés, etc.) está sempre no estado correto
  updateSaida();

  // Pisca o LED e lê o sensor em intervalos regulares
  if ((currentMillis - lastLedMillis) >= ledInterval) {
    //lastLedMillis = currentMillis;
    lastLedMillis = millis();
    readSensor();
    piscaLed();
  }

  // Envia dados se o tempo sendInterval tiver passado OU se o estado foi alterado.
  if ((currentMillis - lastSendMillis) >= sendInterval || shouldSendDataNow == HIGH) {
    //lastSendMillis = currentMillis; // Reseta o timer principal
    lastSendMillis = millis();
    shouldSendDataNow = LOW; // Reseta a flag após o envio
    sendDataToDjango();    
  }

  // Verifica comandos do servidor em um intervalo específico
  if ((currentMillis - lastCheckCommandMillis) >= checkCommandInterval) {
    //lastCheckCommandMillis = currentMillis;
    lastCheckCommandMillis = millis();
    receiveCommandsFromDjango();
  }
}