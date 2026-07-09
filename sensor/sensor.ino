#include "M5StickCPlus2.h"
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// Adres MAC odbiornika. Zastąp właściwym.
uint8_t peerAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Struktura pakietu danych
typedef struct struct_message {
    float x;
    float y;
    float z;
} struct_message;

// Współdzielone zmienne (volatile, ponieważ są używane przez dwa rdzenie)
volatile struct_message myData;
esp_now_peer_info_t peerInfo;

// Zmienne czasowe dla 200 Hz
unsigned long lastImuTime = 0;
const unsigned long imuInterval = 5000; // 5000 µs = 200 Hz

// Deklaracja zadania dla rdzenia 0
TaskHandle_t DisplayTaskHandle;

// Zadanie FreeRTOS obsługujące ekran i baterię (uruchamiane na rdzeniu 0)
void displayTask(void * pvParameters) {
    for(;;) {
        // Odczyt baterii po I2C (operacja blokująca)
        int bat = StickCP2.Power.getBatteryLevel(); 
        
        // Renderowanie tekstu po SPI (operacja blokująca)
        StickCP2.Display.setCursor(0, 40);
        StickCP2.Display.clear();  
        StickCP2.Display.printf("BAT: %d%%\nX: %0.2f\nY: %0.2f\nZ: %0.2f\r\n", 
                                bat, myData.x, myData.y, myData.z);
                                
        // Uśpienie zadania na 200 ms (5 Hz) - zwalnia zasoby rdzenia 0
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

void setup() {
    auto cfg = M5.config();
    StickCP2.begin(cfg);
    StickCP2.Display.setRotation(0);
    StickCP2.Display.setTextColor(GREEN);
    StickCP2.Display.setTextDatum(top_left);
    StickCP2.Display.setFont(&fonts::FreeSansBold9pt7b);
    StickCP2.Display.setTextSize(1);
    StickCP2.Display.println("TX 200Hz");

    // 1. Inicjalizacja WiFi w trybie stacji
    WiFi.mode(WIFI_STA);

    // 2. KRYTYCZNE: Wyłączenie oszczędzania energii WiFi (brak opóźnień w radiu)
    esp_wifi_set_ps(WIFI_PS_NONE);

    // 3. Inicjalizacja ESP-NOW
    if (esp_now_init() != ESP_OK) {
        StickCP2.Display.println("ESP-NOW Error");
        while(1);
    }

    // 4. Konfiguracja odbiornika
    memcpy(peerInfo.peer_addr, peerAddress, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);

    // 5. Uruchomienie zadania obsługi ekranu na osobnym rdzeniu (Core 0)
    // Parametry: funkcja, nazwa, rozmiar stosu, parametry, priorytet, uchwyt, numer rdzenia
    xTaskCreatePinnedToCore(
        displayTask,   
        "DisplayTask", 
        4096,          
        NULL,          
        1,             
        &DisplayTaskHandle, 
        0              
    );

    lastImuTime = micros();
}

void loop() {
    // StickCP2.update() aktualizuje stan przycisków
    StickCP2.update(); 

    unsigned long currentMicros = micros();
    
    // Rygorystyczny timer 5 ms (200 Hz) na rdzeniu 1
    if (currentMicros - lastImuTime >= imuInterval) {
        lastImuTime = currentMicros;

        if (StickCP2.Imu.update()) {
            auto data = StickCP2.Imu.getImuData();

            // Zapis danych (odczytywane asynchronicznie przez rdzeń 0)
            myData.x = data.accel.x;
            myData.y = data.accel.y;
            myData.z = data.accel.z;

            // Wysyłanie pakietu przez ESP-NOW
            esp_now_send(peerAddress, (uint8_t *) &myData, sizeof(myData));
        }
    }
}