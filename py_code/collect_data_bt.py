import sys
import csv
import time
import struct
import asyncio
from collections import deque

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from bleak import BleakClient, BleakScanner


# ============================================================
# KONFIGURACJA
# ============================================================

DEVICE_NAME = "M5Stick_IMU_BLE"

CHARACTERISTIC_UUID = (
    "beb5483e-36e1-4688-b7f5-ea07361b26a8"
)

BATCH_SIZE = 10

MAX_POINTS = 1000

CSV_FILENAME = (
    f"dane_imu_{int(time.time())}.csv"
)


# ============================================================
# BUFOR WYKRESU
# ============================================================

data_x = deque(
    [0.0] * MAX_POINTS,
    maxlen=MAX_POINTS
)

data_y = deque(
    [0.0] * MAX_POINTS,
    maxlen=MAX_POINTS
)

data_z = deque(
    [0.0] * MAX_POINTS,
    maxlen=MAX_POINTS
)


# ============================================================
# QT
# ============================================================

app = QtWidgets.QApplication(sys.argv)

win = pg.GraphicsLayoutWidget(
    title="Wykres Real-time BLE"
)

win.resize(1920, 1080)


try:

    flag_on_top = (
        QtCore.Qt.WindowType.WindowStaysOnTopHint
    )

except AttributeError:

    flag_on_top = (
        QtCore.Qt.WindowStaysOnTopHint
    )


win.setWindowFlags(
    win.windowFlags() | flag_on_top
)

win.show()
win.raise_()
win.activateWindow()


# ============================================================
# OBSŁUGA Q
# ============================================================

def keyPressEvent(event):

    if event.text().lower() == "q":
        app.quit()


win.keyPressEvent = keyPressEvent


# ============================================================
# WYKRES
# ============================================================

plot = win.addPlot(
    title=(
        f"Dane z akcelerometru "
        f"(Zapis do: {CSV_FILENAME})"
    )
)

plot.setYRange(-5, 5)

plot.addLegend()

curve_x = plot.plot(
    pen="r",
    name="X"
)

curve_y = plot.plot(
    pen="g",
    name="Y"
)

curve_z = plot.plot(
    pen="b",
    name="Z"
)


# ============================================================
# WĄTEK BLE
# ============================================================

class BLEReaderThread(QtCore.QThread):

    # Lista:
    # [(x1,y1,z1), ...]
    data_received = QtCore.pyqtSignal(list)

    status_msg = QtCore.pyqtSignal(str)

    # ========================================================
    # NOWY SYGNAŁ:
    #
    # samples_per_second
    # packets_per_second
    # total_samples
    # ========================================================

    stats_received = QtCore.pyqtSignal(
        float,
        float,
        int
    )


    def __init__(self, filename):

        super().__init__()

        self.filename = filename

        self.running = True

        self.loop = None

        # ====================================================
        # LICZNIKI
        # ====================================================

        self.total_samples = 0
        self.total_packets = 0

        self.interval_samples = 0
        self.interval_packets = 0

        self.last_rate_time = time.perf_counter()


    # ========================================================
    # START THREAD
    # ========================================================

    def run(self):

        self.loop = asyncio.new_event_loop()

        asyncio.set_event_loop(
            self.loop
        )

        self.loop.run_until_complete(
            self.ble_task()
        )


    # ========================================================
    # BLE
    # ========================================================

    async def ble_task(self):

        self.status_msg.emit(
            "Skanowanie w poszukiwaniu urządzenia..."
        )

        device = await BleakScanner.find_device_by_name(
            DEVICE_NAME
        )

        if not device:

            self.status_msg.emit(
                "Nie znaleziono urządzenia BLE."
            )

            return


        self.status_msg.emit(
            f"Znaleziono {device.address}. Łączenie..."
        )


        try:

            async with BleakClient(device) as client:

                self.status_msg.emit(
                    "Połączono. Odczyt danych..."
                )


                with open(
                    self.filename,
                    mode="a",
                    newline=""
                ) as file:

                    writer = csv.writer(file)

                    writer.writerow(
                        ["X", "Y", "Z"]
                    )


                    # ========================================
                    # CALLBACK BLE
                    # ========================================

                    def notification_handler(
                        sender,
                        data
                    ):

                        # 10 próbek
                        # 3 floaty
                        # 4 bajty / float
                        #
                        # 10 * 3 * 4 = 120 bajtów

                        if len(data) != 120:

                            print(
                                "Niepoprawny rozmiar "
                                f"paczki: {len(data)}"
                            )

                            return


                        # ====================================
                        # DEKODOWANIE
                        # ====================================

                        unpacked = struct.unpack(
                            "<30f",
                            data
                        )

                        batch = []


                        for i in range(BATCH_SIZE):

                            x = unpacked[
                                i * 3
                            ]

                            y = unpacked[
                                i * 3 + 1
                            ]

                            z = unpacked[
                                i * 3 + 2
                            ]


                            batch.append(
                                (x, y, z)
                            )


                            writer.writerow(
                                [x, y, z]
                            )


                        # ====================================
                        # LICZNIKI
                        # ====================================

                        self.total_packets += 1

                        self.total_samples += (
                            BATCH_SIZE
                        )

                        self.interval_packets += 1

                        self.interval_samples += (
                            BATCH_SIZE
                        )


                        # ====================================
                        # POMIAR CZĘSTOTLIWOŚCI
                        # ====================================

                        now = time.perf_counter()

                        elapsed = (
                            now
                            -
                            self.last_rate_time
                        )


                        if elapsed >= 1.0:

                            samples_per_second = (
                                self.interval_samples
                                /
                                elapsed
                            )

                            packets_per_second = (
                                self.interval_packets
                                /
                                elapsed
                            )


                            # ================================
                            # EMITOWANIE DO GUI
                            # ================================

                            self.stats_received.emit(
                                samples_per_second,
                                packets_per_second,
                                self.total_samples
                            )


                            # ================================
                            # TERMINAL
                            # ================================

                            print(
                                f"REAL DATA RATE: "
                                f"{samples_per_second:7.1f} Hz"
                                f" | BLE: "
                                f"{packets_per_second:5.1f} paczek/s"
                                f" | total: "
                                f"{self.total_samples}"
                            )


                            # ================================
                            # RESET LICZNIKA 1-sekundowego
                            # ================================

                            self.interval_samples = 0

                            self.interval_packets = 0

                            self.last_rate_time = now


                        # ====================================
                        # WYKRES
                        # ====================================

                        self.data_received.emit(
                            batch
                        )


                    # ========================================
                    # START NOTIFY
                    # ========================================

                    await client.start_notify(
                        CHARACTERISTIC_UUID,
                        notification_handler
                    )


                    # ========================================
                    # GŁÓWNA PĘTLA
                    # ========================================

                    while (
                        self.running
                        and
                        client.is_connected
                    ):

                        await asyncio.sleep(
                            0.1
                        )


                    await client.stop_notify(
                        CHARACTERISTIC_UUID
                    )


        except Exception as e:

            self.status_msg.emit(
                f"Błąd BLE: {e}"
            )


    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        self.running = False


# ============================================================
# UPDATE WYKRESU
# ============================================================

def update_plot(batch):

    for x, y, z in batch:

        data_x.append(x)
        data_y.append(y)
        data_z.append(z)


    curve_x.setData(
        list(data_x)
    )

    curve_y.setData(
        list(data_y)
    )

    curve_z.setData(
        list(data_z)
    )


# ============================================================
# STATUS
# ============================================================

def update_title(msg):

    plot.setTitle(msg)


# ============================================================
# NOWE:
# WYŚWIETLANIE RZECZYWISTEGO DATA RATE
# ============================================================

def update_stats(
    sample_rate,
    packet_rate,
    total_samples
):

    plot.setTitle(

        f"IMU: {sample_rate:.1f} Hz"
        f" | BLE: {packet_rate:.1f} paczek/s"
        f" | próbek: {total_samples}"
        f" | {CSV_FILENAME}"

    )


# ============================================================
# START BLE
# ============================================================

try:

    ble_thread = BLEReaderThread(
        CSV_FILENAME
    )


    ble_thread.data_received.connect(
        update_plot
    )


    ble_thread.status_msg.connect(
        update_title
    )


    ble_thread.stats_received.connect(
        update_stats
    )


    ble_thread.start()


except Exception as e:

    print(
        f"Błąd inicjalizacji: {e}"
    )

    sys.exit(1)


# ============================================================
# CLEANUP
# ============================================================

def cleanup():

    ble_thread.stop()

    ble_thread.wait()


app.aboutToQuit.connect(
    cleanup
)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    sys.exit(
        app.exec()
    )