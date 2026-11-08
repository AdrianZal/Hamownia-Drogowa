
#include "M5StickCPlus2.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// UUID dla serwisu i charakterystyki
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

#define BATCH_SIZE 10

// Struktura pojedynczej próbki (12 bajtów)
typedef struct {
    float x;
    float y;
    float z;
} imu_sample_t;

// Struktura paczki danych przesyłanej przez kolejkę (120 bajtów)
typedef struct {
    imu_sample_t samples[BATCH_SIZE];
} imu_batch_t;

// Globalne bufory i wskaźniki
imu_sample_t imuBatch[BATCH_SIZE];
volatile int sampleIndex = 0;

// Uchwyt do kolejki FreeRTOS
QueueHandle_t bleQueue;

// Zmienne współdzielone dla zadania ekranu (do podglądu, używamy volatile)
volatile float lastX = 0, lastY = 0, lastZ = 0;

// Stan BLE
BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

// Zmienne czasowe dla rygorystycznego timera (Core 1)
const unsigned long imuInterval = 2000; // 5000 µs = 200 Hz
unsigned long lastImuTime = 0;

//Ekran
volatile bool screenEnabled = true;

// Callbacki serwera BLE do śledzenia stanu połączenia
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
    }
    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;
    }
};

// ---------------------------------------------------------
// ZADANIA FREERTOS (CORE 0)
// ---------------------------------------------------------

// Zadanie obsługi ekranu (Priorytet 1, Core 0)
void displayTask(void * pvParameters) {
    bool previousScreenState = true;

    StickCP2.Display.setTextColor(GREEN, BLACK);

    for (;;) {
        bool enabled = screenEnabled;

        if (enabled != previousScreenState) {
            StickCP2.Display.setBrightness(enabled ? 50 : 0);
            previousScreenState = enabled;
        }

        if (enabled) {
            int bat = StickCP2.Power.getBatteryLevel();

            StickCP2.Display.setCursor(0, 40);

            StickCP2.Display.printf(
                "BAT: %3d%%  \n"
                ">X: %7.2f  \n"
                "^Y: %7.2f  \n"
                "*Z: %7.2f  \n"
                "BLE: %-4s  \n",
                bat, lastX, lastY, lastZ,
                deviceConnected ? "CONN" : "DISC"
            );
        }

        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

// Zadanie wysyłania paczek BLE (Priorytet 2, Core 0)
// Przejęcie wywołania notify(), aby zapobiec opóźnieniom odczytów w pętli loop()
void bleSendTask(void * pvParameters) {
    imu_batch_t batchToSend;
    for(;;) {
        // xQueueReceive usypia to zadanie do momentu pojawienia się danych w kolejce.
        // Czas oczekiwania portMAX_DELAY oznacza brak limitu (czeka w nieskończoność).
        // Dzięki temu zadanie nie zużywa cykli procesora, gdy czeka.
        if (xQueueReceive(bleQueue, &batchToSend, portMAX_DELAY) == pdPASS) {
            if (deviceConnected) {
                pCharacteristic->setValue((uint8_t*)&batchToSend, sizeof(imu_batch_t));
                pCharacteristic->notify(); // Może blokować, ale dzieje się to na Core 0
            }
        }
    }
}

// ---------------------------------------------------------
// INICJALIZACJA
// ---------------------------------------------------------

void setup() {
    auto cfg = M5.config();
    StickCP2.begin(cfg);
    StickCP2.Display.setBrightness(50);
    StickCP2.Display.setRotation(0);
    StickCP2.Display.setTextColor(GREEN);
    StickCP2.Display.setTextDatum(top_left);
    StickCP2.Display.setFont(&fonts::FreeSansBold9pt7b);
    StickCP2.Display.setTextSize(1);
    StickCP2.Display.println("Sample 500Hz");
    StickCP2.Display.println("BLE 50Hz");
    delay(1000);
    StickCP2.Display.clear();

    // Inicjalizacja BLE
    BLEDevice::init("M5Stick_IMU_BLE");
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());

    BLEService *pService = pServer->createService(SERVICE_UUID);

    // Utworzenie charakterystyki z właściwością NOTIFY
    pCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );

    // Descriptor wymagany do włączenia notyfikacji po stronie klienta
    pCharacteristic->addDescriptor(new BLE2902());

    pService->start();
    
    // Konfiguracja rozgłaszania
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x0);
    BLEDevice::startAdvertising();

    // Utworzenie kolejki na 5 pełnych paczek (chroni przed gubieniem przy chwilowych lagach)
    bleQueue = xQueueCreate(5, sizeof(imu_batch_t)); 

    // Uruchomienie zadań na Core 0 (pętla loop działa domyślnie na Core 1)
    xTaskCreatePinnedToCore(bleSendTask, "BLESendTask", 4096, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(displayTask, "DisplayTask", 4096, NULL, 1, NULL, 0);

    lastImuTime = micros();
}

// ---------------------------------------------------------
// PĘTLA GŁÓWNA (CORE 1) - TYLKO KRYTYCZNE ZBIERANIE DANYCH
// ---------------------------------------------------------

void loop() {
    StickCP2.update(); 
    if (StickCP2.BtnA.wasPressed()) {
        screenEnabled = !screenEnabled;
    }

    // Obsługa ponownego rozgłaszania (re-advertising) po rozłączeniu
    if (!deviceConnected && oldDeviceConnected) {
        pServer->startAdvertising();
        oldDeviceConnected = deviceConnected;
    }
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
    }

    unsigned long currentMicros = micros();
    
    // Rygorystyczny timer 2 ms (500 Hz) na Core 1
    if (currentMicros - lastImuTime >= imuInterval) {
        lastImuTime += imuInterval;

        if (StickCP2.Imu.update()) {
            auto data = StickCP2.Imu.getImuData();

            // Zapis do lokalnego bufora
            imuBatch[sampleIndex].x = data.accel.x;
            imuBatch[sampleIndex].y = data.accel.y;
            imuBatch[sampleIndex].z = data.accel.z;
            
            // Aktualizacja zmiennych do podglądu na ekranie
            lastX = data.accel.x;
            lastY = data.accel.y;
            lastZ = data.accel.z;

            sampleIndex++;

            // Po uzbieraniu BATCH_SIZE (10) próbek, delegujemy wysyłanie do Core 0
            if (sampleIndex >= BATCH_SIZE) {
                imu_batch_t newBatch;
                // Kopiowanie danych do nowej struktury wysyłanej do kolejki
                memcpy(newBatch.samples, (const void*)imuBatch, sizeof(imuBatch));
                
                // xQueueSend z parametrem 0 = NIE BLOKUJ. 
                // Jeśli kolejka jest pełna, paczka przepada, ale utrzymujemy interwał 5ms dla nowych pomiarów.
                xQueueSend(bleQueue, &newBatch, 0);
                
                sampleIndex = 0; 
            }
        }
    }
}
