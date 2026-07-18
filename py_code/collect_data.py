import sys
import csv
import time
from collections import deque
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
import serial

BAUD = 115200
PORT = 'COM' + input("Podaj numer portu COM: ")
MAX_POINTS = 100
CSV_FILENAME = f"dane_imu_{int(time.time())}.csv"

data_x = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
data_y = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
data_z = deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title="Wykres Real-time")
win.resize(1920, 1080)

try:
    flag_on_top = QtCore.Qt.WindowType.WindowStaysOnTopHint
except AttributeError:
    flag_on_top = QtCore.Qt.WindowStaysOnTopHint

win.setWindowFlags(win.windowFlags() | flag_on_top)
win.show()
win.raise_()
win.activateWindow()

def keyPressEvent(event):
    if event.text().lower() == 'q':
        app.quit()

win.keyPressEvent = keyPressEvent

plot = win.addPlot(title=f"Dane z akcelerometru (Zapis do: {CSV_FILENAME})")
plot.setYRange(-5, 5)
plot.addLegend()

curve_x = plot.plot(pen='r', name='X')
curve_y = plot.plot(pen='g', name='Y')
curve_z = plot.plot(pen='b', name='Z')


def parse_line(line):
    try:
        parts = line.replace('R:', '').replace('X:', '').replace('Y:', '').replace('Z:', '').split('|')
        return [float(p) for p in parts]
    except:
        return None


class SerialReaderThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(list)

    def __init__(self, port, baud, filename):
        super().__init__()
        self.port = port
        self.baud = baud
        self.filename = filename
        self.running = True
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
        self.ser.flushInput()

    def run(self):
        with open(self.filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['X', 'Y', 'Z'])  # Zapis nagłówka

            while self.running:
                if self.ser.in_waiting > 0:
                    try:
                        line_raw = self.ser.readline()
                        line = line_raw.decode('utf-8').rstrip()
                        values = parse_line(line)
                        if values:
                            writer.writerow(values)
                            self.data_received.emit(values)
                    except (UnicodeDecodeError, serial.SerialException):
                        continue
        self.ser.close()

    def stop(self):
        self.running = False


def update_plot(values):
    data_x.append(values[0])
    data_y.append(values[1])
    data_z.append(values[2])

    curve_x.setData(list(data_x))
    curve_y.setData(list(data_y))
    curve_z.setData(list(data_z))


try:
    serial_thread = SerialReaderThread(PORT, BAUD, CSV_FILENAME)
    serial_thread.data_received.connect(update_plot)
    serial_thread.start()
except Exception as e:
    print(f"Błąd: {e}")
    sys.exit(1)


def cleanup():
    serial_thread.stop()
    serial_thread.wait()

app.aboutToQuit.connect(cleanup)

if __name__ == '__main__':
    sys.exit(app.exec())