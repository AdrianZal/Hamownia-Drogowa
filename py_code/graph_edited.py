import sys
import csv
import numpy as np
import pyqtgraph as pg

from scipy.signal import (
    butter,
    sosfiltfilt,
    stft,
    istft,
    hilbert,
    savgol_filter
)

from scipy.ndimage import median_filter
from pyqtgraph.Qt import QtWidgets

# ============================================================
# OPONA / SKRZYNIA 02M DIESEL 4MOTION
# ============================================================

# Opona 225/45 R18
TIRE_WIDTH_MM = 225.0
TIRE_ASPECT_RATIO = 0.45
RIM_DIAMETER_IN = 18.0

# Całkowite przełożenie silnik -> koło
TOTAL_GEAR_RATIO = 5.131

# ============================================================
# USTAWIENIA
# ============================================================

FS = 500.0
TRACK_MIN_HZ = 5.0
TRACK_MAX_HZ = 50.0

PRE_FILTER_LOW = 0.3
PRE_FILTER_HIGH = 80.0
PRE_FILTER_ORDER = 4

# ============================================================
# SZYBSZY TRACKER
# ============================================================

STFT_NPERSEG = 256
STFT_NOVERLAP = 248
STFT_NFFT = 4096

MAX_TRACK_STEP_HZ = 1.5
TRACK_CONTINUITY_WEIGHT = 0.2

# ============================================================
# FILTR ADAPTACYJNY
# ============================================================

TRACK_BANDWIDTH_HZ = 4.0

# ============================================================
# KOMPENSACJA ŚRODKA
# ============================================================

BASELINE_CUTOFF_HZ = 0.20
BASELINE_FIT_MIN_HZ = 1.5
BASELINE_CONFIDENCE_MIN = 8.0

# ============================================================
# NORMALIZACJA
# ============================================================

NORMALIZE_AMPLITUDE = True
AMPLITUDE_FILTER_HZ = 1.0
MIN_AMPLITUDE = 0.05

# ============================================================
# RPM
# ============================================================

RPM_FILTER_HZ = 3.0
ANGLE_OFFSET_DEG = 0.0

# ============================================================
# FUNKCJE
# ============================================================

def bandpass_filter(signal):
    sos = butter(
        PRE_FILTER_ORDER,
        [PRE_FILTER_LOW, PRE_FILTER_HIGH],
        btype="bandpass",
        fs=FS,
        output="sos"
    )
    return sosfiltfilt(sos, signal)

def lowpass_filter(signal, cutoff, order=2):
    sos = butter(
        order,
        cutoff,
        btype="lowpass",
        fs=FS,
        output="sos"
    )
    return sosfiltfilt(sos, signal)

def refine_frequency(freq, spectrum, index):
    if index <= 0 or index >= len(spectrum) - 1:
        return freq[index]

    y1 = np.log(spectrum[index - 1] + 1e-12)
    y2 = np.log(spectrum[index] + 1e-12)
    y3 = np.log(spectrum[index + 1] + 1e-12)

    denominator = (y1 - 2.0 * y2 + y3)

    if abs(denominator) < 1e-12:
        return freq[index]

    delta = 0.5 * (y1 - y3) / denominator
    delta = np.clip(delta, -0.5, 0.5)
    df = freq[1] - freq[0]

    return freq[index] + delta * df

def track_frequency(signal):
    frequencies, frame_time, Z = stft(
        signal,
        fs=FS,
        window="hann",
        nperseg=STFT_NPERSEG,
        noverlap=STFT_NOVERLAP,
        nfft=STFT_NFFT,
        boundary="zeros",
        padded=True
    )

    mask = (frequencies >= TRACK_MIN_HZ) & (frequencies <= TRACK_MAX_HZ)
    freq_track = frequencies[mask]
    magnitude = np.abs(Z[mask, :])

    tracked = np.zeros(magnitude.shape[1])
    confidence = np.zeros(magnitude.shape[1])
    previous_frequency = None

    for frame in range(magnitude.shape[1]):
        spectrum = magnitude[:, frame]
        noise_level = np.median(spectrum) + 1e-12
        normalized = spectrum / noise_level

        if previous_frequency is None:
            best_index = np.argmax(spectrum)
        else:
            frequency_difference = freq_track - previous_frequency
            allowed = np.abs(frequency_difference) <= MAX_TRACK_STEP_HZ

            score = (
                np.log(normalized + 1e-12)
                - TRACK_CONTINUITY_WEIGHT * frequency_difference ** 2
            )
            score[~allowed] = -np.inf

            if not np.any(np.isfinite(score)):
                best_index = np.argmax(spectrum)
            else:
                best_index = np.argmax(score)

        best_frequency = refine_frequency(freq_track, spectrum, best_index)
        tracked[frame] = best_frequency
        previous_frequency = best_frequency
        confidence[frame] = spectrum[best_index] / noise_level

    tracked = median_filter(
        tracked,
        size=5,
        mode="nearest"
    )

    tracked = savgol_filter(
        tracked,
        window_length=15,
        polyorder=2
    )

    return frequencies, frame_time, Z, tracked, confidence

def interpolate_tracker(time, frame_time, tracked, confidence):
    tracked_sample = np.interp(
        time, frame_time, tracked, left=tracked[0], right=tracked[-1]
    )
    confidence_sample = np.interp(
        time, frame_time, confidence, left=confidence[0], right=confidence[-1]
    )
    return tracked_sample, confidence_sample

def fit_centripetal_baseline(x, tracked_hz, confidence, time):
    baseline_slow = lowpass_filter(x, BASELINE_CUTOFF_HZ, order=3)
    frequency_squared = tracked_hz ** 2

    edge_mask = (time > 2.0) & (time < time[-1] - 2.0)

    valid = (
        edge_mask
        & (tracked_hz >= BASELINE_FIT_MIN_HZ)
        & (confidence >= BASELINE_CONFIDENCE_MIN)
        & np.isfinite(baseline_slow)
        & np.isfinite(frequency_squared)
    )

    if np.sum(valid) < 200:
        valid = (
            edge_mask
            & (tracked_hz >= BASELINE_FIT_MIN_HZ)
            & np.isfinite(baseline_slow)
        )

    if np.sum(valid) >= 100 and np.std(frequency_squared[valid]) > 1e-3:
        K, B0 = np.polyfit(frequency_squared[valid], baseline_slow[valid], 1)
    else:
        print("UWAGA: za mało zmian prędkości do dokładnej kalibracji K.")
        K = 0.0
        B0 = np.median(baseline_slow)

    predicted_baseline = B0 + K * frequency_squared
    return B0, K, predicted_baseline, baseline_slow

def adaptive_filter(signal, tracked_frame_time, tracked_frequency):
    frequencies, frame_time, Z = stft(
        signal,
        fs=FS,
        window="hann",
        nperseg=STFT_NPERSEG,
        noverlap=STFT_NOVERLAP,
        nfft=STFT_NFFT,
        boundary="zeros",
        padded=True
    )

    center_frequency = np.interp(
        frame_time, tracked_frame_time, tracked_frequency,
        left=tracked_frequency[0], right=tracked_frequency[-1]
    )

    frequency_matrix = frequencies[:, None]
    center_matrix = center_frequency[None, :]

    adaptive_mask = np.exp(
        -0.5 * ((frequency_matrix - center_matrix) / TRACK_BANDWIDTH_HZ) ** 2
    )

    valid = (frequencies >= 0.2) & (frequencies <= min(TRACK_MAX_HZ + 10.0, FS / 2.0 - 1.0))
    adaptive_mask[~valid, :] = 0.0

    Z_filtered = Z * adaptive_mask

    _, filtered = istft(
        Z_filtered,
        fs=FS,
        window="hann",
        nperseg=STFT_NPERSEG,
        noverlap=STFT_NOVERLAP,
        nfft=STFT_NFFT,
        input_onesided=True,
        boundary=True
    )

    return filtered

# ============================================================
# ODCZYT CSV
# ============================================================

CSV_FILENAME = input("Podaj nazwę pliku CSV (np. dane_imu_1234567890.csv): ")

x_data, y_data, z_data = [], [], []

try:
    with open(CSV_FILENAME, mode="r") as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if len(row) >= 3:
                x_data.append(float(row[0]))
                y_data.append(float(row[1]))
                z_data.append(float(row[2]))
except FileNotFoundError:
    print("Nie znaleziono pliku.")
    sys.exit(1)
except Exception as e:
    print(f"Błąd odczytu: {e}")
    sys.exit(1)

x = np.asarray(x_data, dtype=float)
if len(x) < STFT_NPERSEG:
    print("Za mało danych do analizy.")
    sys.exit(1)

time = np.arange(len(x)) / FS

# ============================================================
# PRZETWARZANIE
# ============================================================

print("\nPASS 1 - wstępne śledzenie częstotliwości...")
x_pre_rough = bandpass_filter(x)
freq1, frame_time1, Z1, tracked1, confidence1 = track_frequency(x_pre_rough)
tracked_hz_rough, confidence_rough = interpolate_tracker(time, frame_time1, tracked1, confidence1)

print("Estymacja przesunięcia środka sinusoidy...")
B0_rough, K_rough, baseline_rough, baseline_slow_rough = fit_centripetal_baseline(
    x, tracked_hz_rough, confidence_rough, time
)
x_centered_rough = x - baseline_rough

print("PASS 2 - dokładne śledzenie częstotliwości...")
x_pre_centered = bandpass_filter(x_centered_rough)
freq2, frame_time2, Z2, tracked2, confidence2 = track_frequency(x_pre_centered)
tracked_hz, confidence = interpolate_tracker(time, frame_time2, tracked2, confidence2)

print("Finalna kalibracja B0 + K*f^2...")
B0, K, centripetal_baseline, baseline_slow = fit_centripetal_baseline(x, tracked_hz, confidence, time)
x_centered = x - centripetal_baseline

x_pre_corrected = bandpass_filter(x_centered)

print("Adaptacyjna filtracja sinusoidy...")
x_adaptive = adaptive_filter(x_pre_corrected, frame_time2, tracked2)

if len(x_adaptive) > len(x):
    x_adaptive = x_adaptive[:len(x)]
elif len(x_adaptive) < len(x):
    x_adaptive = np.pad(x_adaptive, (0, len(x) - len(x_adaptive)))

analytic_temp = hilbert(x_adaptive)
amplitude_raw = np.abs(analytic_temp)
amplitude_smooth = lowpass_filter(amplitude_raw, AMPLITUDE_FILTER_HZ, order=2)
amplitude_safe = np.maximum(amplitude_smooth, MIN_AMPLITUDE)

if NORMALIZE_AMPLITUDE:
    x_normalized = x_adaptive / amplitude_safe
else:
    x_normalized = x_adaptive.copy()

analytic_signal = hilbert(x_normalized)
phase = np.unwrap(np.angle(analytic_signal))
phase_relative = phase - phase[0]
angle_deg = (np.degrees(phase_relative) + ANGLE_OFFSET_DEG) % 360.0

instant_frequency = savgol_filter(
    phase,
    window_length=101,
    polyorder=3,
    deriv=1,
    delta=1.0 / FS,
    mode="interp"
) / (2.0 * np.pi)

rpm_phase_raw = instant_frequency * 60.0

rpm_phase_median = median_filter(
    rpm_phase_raw,
    size=7,
    mode="nearest"
)

rpm_phase = lowpass_filter(
    rpm_phase_median,
    cutoff=2.0,
    order=2
)

rpm_tracker = tracked_hz * 60.0
rpm_phase_positive = np.maximum(rpm_phase, 0.0)
engine_rpm = rpm_phase_positive * TOTAL_GEAR_RATIO

# ============================================================
# GEOMETRIA KOŁA I PRĘDKOŚĆ POJAZDU
# ============================================================

sidewall_m = TIRE_WIDTH_MM * TIRE_ASPECT_RATIO / 1000.0
rim_diameter_m = RIM_DIAMETER_IN * 0.0254
wheel_diameter_m = rim_diameter_m + 2.0 * sidewall_m
wheel_circumference_m = np.pi * wheel_diameter_m

wheel_rps = rpm_phase_positive / 60.0
vehicle_speed_mps = wheel_rps * wheel_circumference_m
vehicle_speed_kmh = vehicle_speed_mps * 3.6

# ============================================================
# INFORMACJE
# ============================================================

print("\n============================================")
print(" WYNIKI ANALIZY")
print("============================================")
print(f"Częstotliwość próbkowania: {FS:.1f} Hz")
print(f"Liczba próbek:            {len(x)}")
print(f"Czas nagrania:            {time[-1]:.2f} s\n")

print("MODEL PRZESUNIĘCIA ŚRODKA:")
print(f"B0 = {B0:.6f}")
print(f"K  = {K:.9f}\n")
print("baseline(f) = B0 + K * f^2\n")

print(f"Min częstotliwość:        {np.min(tracked_hz):.2f} Hz")
print(f"Max częstotliwość:        {np.max(tracked_hz):.2f} Hz")
print(f"Średnia częstotliwość:    {np.mean(tracked_hz):.2f} Hz\n")

print(f"Max RPM tracker:          {np.max(rpm_tracker):.1f}")
print(f"Średnie RPM tracker:      {np.mean(rpm_tracker):.1f}")
print(f"Max RPM z fazy:           {np.max(rpm_phase):.1f}")
print(f"Średnie RPM z fazy:       {np.mean(rpm_phase):.1f}\n")

print(f"Przełożenie całkowite:    {TOTAL_GEAR_RATIO:.5f}")
print(f"Max RPM silnika:          {np.nanmax(engine_rpm):.1f}")
print(f"Max prędkość:             {np.nanmax(vehicle_speed_kmh):.1f} km/h\n")

print("Sinusoida po normalizacji:")
print(f"min = {np.min(x_normalized):.3f}")
print(f"max = {np.max(x_normalized):.3f}")
print("============================================")

# ============================================================
# PYQTGRAPH
# ============================================================

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(title=f"Analiza obrotów koła - {CSV_FILENAME}")
win.resize(1500, 1000)
win.show()

# Wykres 1
plot_signal = win.addPlot(title="Porównanie X: po kompensacji / filtr adaptacyjny / normalizacja")
plot_signal.addLegend()
plot_signal.showGrid(x=True, y=True)
plot_signal.plot(time, x_centered, pen=pg.mkPen((120, 120, 255), width=1), name="X po odjęciu środka")
plot_signal.plot(time, x_adaptive, pen=pg.mkPen((0, 220, 255), width=2), name="X filtr adaptacyjny")
plot_signal.plot(time, x_normalized, pen=pg.mkPen((0, 255, 100), width=2), name="X znormalizowane")
plot_signal.addLine(y=1.0, pen=pg.mkPen((100, 100, 100)))
plot_signal.addLine(y=0.0, pen=pg.mkPen((100, 100, 100)))
plot_signal.addLine(y=-1.0, pen=pg.mkPen((100, 100, 100)))

# Wykres 2
win.nextRow()
plot_frequency = win.addPlot(title="Automatycznie śledzona częstotliwość koła")
plot_frequency.showGrid(x=True, y=True)
plot_frequency.setYRange(0, TRACK_MAX_HZ + 5)
plot_frequency.plot(time, tracked_hz, pen=pg.mkPen((255, 200, 0), width=2))

# Wykres 3
win.nextRow()
plot_rpm = win.addPlot(title="Prędkość obrotowa")
plot_rpm.addLegend()
plot_rpm.showGrid(x=True, y=True)
plot_rpm.plot(time, rpm_tracker, pen=pg.mkPen((255, 170, 0), width=2), name="RPM tracker")
plot_rpm.plot(time, rpm_phase, pen=pg.mkPen((0, 200, 255), width=2), name="RPM z fazy")

# Wykres 4 - Prędkość pojazdu
win.nextRow()
plot_speed = win.addPlot(title="Prędkość pojazdu [km/h]")
plot_speed.showGrid(x=True, y=True)
plot_speed.plot(time, vehicle_speed_kmh, pen=pg.mkPen((255, 80, 80), width=2))

# Wykres 5
win.nextRow()
plot_angle = win.addPlot(title="Pozycja koła 0 - 360°")
plot_angle.showGrid(x=True, y=True)
plot_angle.setYRange(0, 360)
plot_angle.plot(time, angle_deg, pen=pg.mkPen((255, 255, 255), width=2))

# Wykres 6
win.nextRow()
plot_confidence = win.addPlot(title="Pewność śledzenia częstotliwości")
plot_confidence.showGrid(x=True, y=True)
plot_confidence.plot(time, confidence, pen=pg.mkPen((200, 100, 255), width=2))

# Synchronizacja osi X
plot_frequency.setXLink(plot_signal)
plot_rpm.setXLink(plot_signal)
plot_speed.setXLink(plot_signal)
plot_angle.setXLink(plot_signal)
plot_confidence.setXLink(plot_signal)

plot_signal.setXRange(time[0], time[-1], padding=0.01)

if __name__ == "__main__":
    sys.exit(app.exec())