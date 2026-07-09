#include <esp_now.h>
#include <WiFi.h>

// Struktura pakietu danych (musi być identyczna jak w nadajniku)
typedef struct struct_message {
    float x;
    float y;
    float z;
} struct_message;

struct_message myData;

// Callback: Wywoływany przy odbiorze danych
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
    memcpy(&myData, incomingData, sizeof(myData));
    Serial.printf("X: %0.4f | Y: %0.4f | Z: %0.4f\n", myData.x, myData.y, myData.z);
}

void setup() {
    Serial.begin(115200);

    // 1. Ustawienie Wi-Fi w tryb Station
    WiFi.mode(WIFI_STA);

    // Wypisanie adresu MAC odbiornika w monitorze portu szeregowego
    Serial.print("Adres MAC tego urządzenia: ");
    Serial.println(WiFi.macAddress());

    // 2. Inicjalizacja ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("Blad inicjalizacji ESP-NOW!");
        while(1);
    }

    // 3. Rejestracja funkcji nasłuchującej
    esp_now_register_recv_cb(OnDataRecv);
    Serial.println("Odbiornik gotowy. Czekam na dane...");
}

void loop() {
    // Odczyt asynchroniczny w tle, pętla pozostaje pusta
    delay(1000);
}