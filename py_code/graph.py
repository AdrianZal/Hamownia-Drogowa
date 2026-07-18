import sys
import csv
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

CSV_FILENAME = input("Podaj nazwę pliku CSV (np. dane_imu_1234567890.csv): ")

x_data, y_data, z_data = [], [], []

try:
    with open(CSV_FILENAME, mode='r') as file:
        reader = csv.reader(file)
        next(reader)  # Pomiń nagłówek
        for row in reader:
            if len(row) == 3:
                x_data.append(float(row[0]))
                y_data.append(float(row[1]))
                z_data.append(float(row[2]))
except FileNotFoundError:
    print("Nie znaleziono pliku.")
    sys.exit(1)
except Exception as e:
    print(f"Błąd odczytu: {e}")
    sys.exit(1)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title=f"Podgląd: {CSV_FILENAME}")
win.resize(1280, 720)
win.show()

plot = win.addPlot(title="Zapisane dane z akcelerometru")
plot.addLegend()
plot.showGrid(x=True, y=True)

time_axis = list(range(len(x_data)))

plot.plot(time_axis, x_data, pen='r', name='X')
plot.plot(time_axis, y_data, pen='g', name='Y')
plot.plot(time_axis, z_data, pen='b', name='Z')

if __name__ == '__main__':
    sys.exit(app.exec())