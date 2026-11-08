#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interaktywna analiza IMU X/Y, zakres śledzenia 2–50 Hz.

Wyświetla 6 wykresów w oknie PyQtGraph jak pierwotny program.
Nie zapisuje i nie modyfikuje żadnych plików (w tym wejściowego CSV).

Uruchomienie:
    python analiza_imu_wykresy_2_50hz.py pomiar.csv
    python analiza_imu_wykresy_2_50hz.py  # pyta o nazwę pliku

Brak czasu w CSV: --fs należy ustawić zgodnie z faktyczną częstotliwością IMU.
Wymagane biblioteki: numpy scipy pyqtgraph oraz PyQt5 / PyQt6 / PySide6.
"""

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import median_filter
from scipy.signal import butter, sosfiltfilt, savgol_filter, stft, hilbert

FS_DEFAULT = 500.0
TIRE_WIDTH_MM = 225.0
TIRE_ASPECT_RATIO = 0.45
RIM_DIAMETER_IN = 18.0
TOTAL_GEAR_RATIO = 5.131

TRACK_MIN_HZ = 2.0
TRACK_MAX_HZ = 50.0
STFT_NPERSEG = 256
STFT_NOVERLAP = 248
STFT_NFFT = 4096
MAX_TRACK_STEP_HZ = 2.0
TRACK_CONTINUITY_WEIGHT = 0.5
BASELINE_FILTER_HZ = 0.22
XY_NOISE_LOWPASS_HZ = 75.0  # zachowuje skladowe sygnalu az do 50 Hz
PHASE_DERIVATIVE_WINDOW = 251   # 0.502 s przy 500 Hz
RPM_LOWPASS_HZ = 2.0


def lowpass(samples, fs, cutoff, order=3):
    sos = butter(order, cutoff, fs=fs, btype="lowpass", output="sos")
    return sosfiltfilt(sos, samples, axis=0)


def bandpass(samples, fs, low, high, order=4):
    sos = butter(order, [low, high], fs=fs, btype="bandpass", output="sos")
    return sosfiltfilt(sos, samples, axis=0)


def track_stft(x, fs, t):
    x_pre = bandpass(x, fs, 0.3, min(80.0, 0.45 * fs))
    f, ft, spectrum = stft(
        x_pre, fs=fs, window="hann", nperseg=STFT_NPERSEG,
        noverlap=STFT_NOVERLAP, nfft=STFT_NFFT,
        boundary=None, padded=False,
    )
    keep = (f >= TRACK_MIN_HZ) & (f <= min(TRACK_MAX_HZ, 0.45 * fs))
    freq = f[keep]
    mag = np.abs(spectrum[keep])
    track = np.empty(mag.shape[1])
    confidence = np.empty_like(track)

    previous = None
    for k in range(mag.shape[1]):
        s = mag[:, k]
        noise = np.median(s) + 1e-12
        if previous is None:
            idx = int(np.argmax(s))
        else:
            diff = freq - previous
            score = np.log(s / noise + 1e-12) - TRACK_CONTINUITY_WEIGHT * diff**2
            score[np.abs(diff) > MAX_TRACK_STEP_HZ] = -np.inf
            idx = int(np.argmax(score)) if np.any(np.isfinite(score)) else int(np.argmax(s))
        best = float(freq[idx])
        if 0 < idx < len(freq) - 1:
            a, b, c = np.log(s[idx-1:idx+2] + 1e-12)
            curvature = a - 2*b + c
            if abs(curvature) > 1e-12:
                best += float(np.clip(0.5*(a-c)/curvature, -0.5, 0.5) * (freq[1]-freq[0]))
        track[k] = best
        confidence[k] = s[idx] / noise
        previous = best

    track = median_filter(track, size=5, mode="nearest")
    track = savgol_filter(track, window_length=11, polyorder=2)
    return np.interp(t, ft, track), np.interp(t, ft, confidence)


def fit_center(xy, track_hz, confidence, fs, t):
    # Średnia składowa odśrodkowa zmienia się z kwadratem częstotliwości.
    baseline_slow = lowpass(xy, fs, BASELINE_FILTER_HZ, order=3)
    f2 = np.square(track_hz)
    valid = (
        (t > 1.0) & (t < t[-1] - 2.0)
        & (track_hz >= TRACK_MIN_HZ) & (confidence >= 3.0)
    )
    if valid.sum() < 100:
        raise ValueError("Zbyt mało wiarygodnych próbek do wyznaczenia środka sygnału X/Y")

    coefficients = []
    for axis in range(2):
        r = least_squares(
            lambda p: p[0] + p[1] * f2[valid] - baseline_slow[valid, axis],
            x0=[0.0, 0.01], loss="soft_l1", f_scale=0.1,
        )
        coefficients.append(r.x)
    coefficients = np.asarray(coefficients)
    center = coefficients[:, 0][None, :] + f2[:, None] * coefficients[:, 1][None, :]
    return center, coefficients


def calculate(data, fs, gear_ratio):
    if fs <= 2 * XY_NOISE_LOWPASS_HZ:
        raise ValueError(f"FS musi przekraczać {2 * XY_NOISE_LOWPASS_HZ:g} Hz dla filtra X/Y 75 Hz")
    if len(data) < STFT_NPERSEG:
        raise ValueError(f"Za mało próbek: potrzeba co najmniej {STFT_NPERSEG}")
    t = np.arange(len(data)) / fs
    x, y = data[:, 0], data[:, 1]
    tracked_hz, confidence = track_stft(x, fs, t)
    center, coefficients = fit_center(data[:, :2], tracked_hz, confidence, fs, t)

    # X i Y są w przybliżeniu sygnałami kwadraturowymi (~90 st. różnicy).
    # Ujemne Y powoduje wzrost fazy w kierunku obrotu z badanego nagrania.
    xy_corrected = lowpass(data[:, :2] - center, fs, XY_NOISE_LOWPASS_HZ, order=4)
    phase = np.unwrap(np.arctan2(-xy_corrected[:, 1], xy_corrected[:, 0]))
    phase_smooth = savgol_filter(phase, 101, 3, mode="interp")
    angle_deg = np.mod(np.degrees(phase_smooth - phase_smooth[0]), 360)

    window = int(round(PHASE_DERIVATIVE_WINDOW * fs / 500.0))
    window = max(11, window + 1 - window % 2)
    if window >= len(t):
        window = len(t) - 1 if len(t) % 2 == 0 else len(t)
    if window % 2 == 0:
        window -= 1
    phase_freq = savgol_filter(
        phase, window_length=window, polyorder=3,
        deriv=1, delta=1/fs, mode="interp"
    ) / (2*np.pi)
    phase_freq = lowpass(phase_freq, fs, RPM_LOWPASS_HZ, order=2)

    # STFT jest odporniejsze na chwilowe zakłócenia X/Y przy większych obrotach.
    # Faza z dwóch osi pomaga przy niskich obrotach, również poniżej 2 Hz.
    mix = np.clip((tracked_hz - TRACK_MIN_HZ) / 2.0, 0.0, 1.0)
    mix = mix * mix * (3 - 2 * mix)
    wheel_hz = np.maximum(mix * tracked_hz + (1 - mix) * phase_freq, 0.0)
    wheel_rpm = wheel_hz * 60
    engine_rpm = wheel_rpm * gear_ratio

    sidewall_m = TIRE_WIDTH_MM * TIRE_ASPECT_RATIO / 1000
    diameter_m = RIM_DIAMETER_IN * 0.0254 + 2 * sidewall_m
    circumference_m = np.pi * diameter_m
    speed_kmh = wheel_hz * circumference_m * 3.6

    return dict(time=t, data=data, center=center, coefficients=coefficients,
                xy_corrected=xy_corrected, angle_deg=angle_deg,
                tracked_hz=tracked_hz, phase_hz=phase_freq,
                wheel_hz=wheel_hz, wheel_rpm=wheel_rpm,
                engine_rpm=engine_rpm, speed_kmh=speed_kmh,
                confidence=confidence, circumference_m=circumference_m)



def show_plots(r, csv_filename, fs):
    """Sześć interaktywnych wykresów — taki sam układ jak w oryginale."""
    try:
        import pyqtgraph as pg
        from pyqtgraph.Qt import QtWidgets
    except ImportError as exc:
        raise SystemExit(
            "Brakuje PyQtGraph lub biblioteki Qt. "
            "Zainstaluj: pip install pyqtgraph PyQt6"
        ) from exc

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    pg.setConfigOptions(antialias=True)
    win = pg.GraphicsLayoutWidget(title=f"Analiza obrotów koła 2–50 Hz — {csv_filename}")
    win.resize(1500, 1000)

    t = r['time']
    x_centered = r['data'][:, 0] - r['center'][:, 0]
    x_filtered = r['xy_corrected'][:, 0]

    # Normalizacja jest tylko podglądem przebiegu — nie zmienia obliczeń RPM.
    envelope = np.abs(hilbert(x_filtered))
    envelope_smooth = lowpass(envelope, fs, 1.0, order=2)
    x_normalized = x_filtered / np.maximum(envelope_smooth, 0.05)

    # Wykres 1: porównanie sygnałów X
    plot_signal = win.addPlot(title="X: kompensacja środka / filtracja / normalizacja")
    plot_signal.addLegend()
    plot_signal.showGrid(x=True, y=True)
    plot_signal.plot(t, x_centered, pen=pg.mkPen((120, 120, 255), width=1),
                     name="X po odjęciu środka")
    plot_signal.plot(t, x_filtered, pen=pg.mkPen((0, 220, 255), width=2),
                     name="X po filtracji")
    plot_signal.plot(t, x_normalized, pen=pg.mkPen((0, 255, 100), width=2),
                     name="X znormalizowane (podgląd)")
    for level in (1.0, 0.0, -1.0):
        plot_signal.addLine(y=level, pen=pg.mkPen((100, 100, 100)))

    # Wykres 2: częstotliwość koła
    win.nextRow()
    plot_frequency = win.addPlot(title="Częstotliwość koła — STFT / faza X/Y / wynik połączony")
    plot_frequency.addLegend()
    plot_frequency.showGrid(x=True, y=True)
    plot_frequency.setYRange(0, TRACK_MAX_HZ + 5)
    plot_frequency.plot(t, r['tracked_hz'], pen=pg.mkPen((255, 200, 0), width=1), name="STFT")
    plot_frequency.plot(t, r['phase_hz'], pen=pg.mkPen((130, 160, 255), width=1), name="Faza X/Y")
    plot_frequency.plot(t, r['wheel_hz'], pen=pg.mkPen((0, 255, 130), width=2), name="Wynik")

    # Wykres 3: RPM koła (jak w oryginale: tracker i faza)
    win.nextRow()
    plot_rpm = win.addPlot(title="Prędkość obrotowa [RPM]")
    plot_rpm.addLegend()
    plot_rpm.showGrid(x=True, y=True)
    plot_rpm.plot(t, 60.0 * r['tracked_hz'], pen=pg.mkPen((255, 170, 0), width=1), name="Koło — STFT")
    plot_rpm.plot(t, 60.0 * r['phase_hz'], pen=pg.mkPen((0, 200, 255), width=1), name="Koło — faza X/Y")
    plot_rpm.plot(t, r['wheel_rpm'], pen=pg.mkPen((0, 255, 120), width=2), name="Koło — wynik")

    # Wykres 4: prędkość pojazdu
    win.nextRow()
    plot_speed = win.addPlot(title="Prędkość pojazdu [km/h] (szacowana)")
    plot_speed.showGrid(x=True, y=True)
    plot_speed.plot(t, r['speed_kmh'], pen=pg.mkPen((255, 80, 80), width=2))

    # Wykres 5: kąt koła
    win.nextRow()
    plot_angle = win.addPlot(title="Pozycja koła 0–360° (względem początku pomiaru)")
    plot_angle.showGrid(x=True, y=True)
    plot_angle.setYRange(0, 360)
    plot_angle.plot(t, r['angle_deg'], pen=pg.mkPen((255, 255, 255), width=2))

    # Wykres 6: pewność trackera
    win.nextRow()
    plot_confidence = win.addPlot(title="Pewność śledzenia częstotliwości — STFT")
    plot_confidence.showGrid(x=True, y=True)
    plot_confidence.plot(t, r['confidence'], pen=pg.mkPen((200, 100, 255), width=2))

    for plot in (plot_frequency, plot_rpm, plot_speed, plot_angle, plot_confidence):
        plot.setXLink(plot_signal)
    plot_signal.setXRange(t[0], t[-1], padding=0.01)

    win.show()
    app.exec()


def main():
    parser = argparse.ArgumentParser(description="Interaktywna analiza IMU 2–50 Hz (tylko wykresy, bez zapisu)")
    parser.add_argument('csv', nargs='?', type=Path, help="Wejściowy CSV z kolumnami X,Y,Z")
    parser.add_argument('--fs', type=float, default=FS_DEFAULT, help="Częstotliwość próbkowania IMU [Hz]")
    parser.add_argument('--gear-ratio', type=float, default=TOTAL_GEAR_RATIO, help="Całkowite przełożenie silnik/koło")
    args = parser.parse_args()

    if args.csv is None:
        raw_name = input("Podaj nazwę pliku CSV: ").strip().strip('\"')
        if not raw_name:
            parser.error("Nie podano pliku CSV")
        args.csv = Path(raw_name)

    if not (np.isfinite(args.fs) and args.fs > max(2 * TRACK_MAX_HZ, 2 * XY_NOISE_LOWPASS_HZ)):
        parser.error(f"--fs musi być > {max(2 * TRACK_MAX_HZ, 2 * XY_NOISE_LOWPASS_HZ):g} Hz")
    if not (np.isfinite(args.gear_ratio) and args.gear_ratio > 0):
        parser.error("--gear-ratio musi być dodatnie")
    try:
        data = np.genfromtxt(args.csv, delimiter=',', skip_header=1)
    except (OSError, ValueError) as exc:
        parser.error(f"Nie można odczytać CSV: {exc}")
    if data.ndim != 2 or data.shape[1] < 3 or data.shape[0] < 700:
        parser.error("Wymagany CSV z co najmniej 700 próbkami i kolumnami X,Y,Z")
    if not np.isfinite(data).all():
        parser.error("Plik zawiera braki lub wartości nienumeryczne")

    try:
        r = calculate(data[:, :3], args.fs, args.gear_ratio)
    except ValueError as exc:
        parser.error(str(exc))

    print(f'Próbek: {len(r["time"])}; długość: {r["time"][-1]:.2f} s przy FS={args.fs:g} Hz')
    print('Zakres śledzenia: 2–50 Hz')
    print('Środek X = B0 + K*f²: B0={:.5f}, K={:.7f}'.format(*r['coefficients'][0]))
    print('Środek Y = B0 + K*f²: B0={:.5f}, K={:.7f}'.format(*r['coefficients'][1]))
    print('Maks. częstotliwość koła: {:.2f} Hz'.format(r['wheel_hz'].max()))
    print('Maks. RPM silnika: {:.0f} obr/min'.format(r['engine_rpm'].max()))
    print('Maks. prędkość: {:.1f} km/h'.format(r['speed_kmh'].max()))
    print('Oryginalny plik CSV nie jest zmieniany. Żadne pliki wynikowe nie są tworzone.')
    show_plots(r, args.csv.name, args.fs)


if __name__ == '__main__':
    main()
