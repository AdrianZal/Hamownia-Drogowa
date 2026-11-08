using Plugin.BLE;
using Plugin.BLE.Abstractions.Contracts;
using Plugin.BLE.Abstractions.EventArgs;
using System.Text;
using System.Collections.ObjectModel;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using LiveChartsCore.SkiaSharpView.Painting;
using SkiaSharp;

namespace MobileApp;

public partial class MainPage : ContentPage
{
    // BLE Config
    private readonly IAdapter _adapter;
    private IDevice _m5StickDevice;
    private ICharacteristic _imuCharacteristic;

    private readonly Guid _serviceId = Guid.Parse("4fafc201-1fb5-459e-8fcc-c5c9c331914b");
    private readonly Guid _characteristicId = Guid.Parse("beb5483e-36e1-4688-b7f5-ea07361b26a8");

    // Stan połączenia
    private bool _isConnected = false;

    // Dane
    private StringBuilder _csvData;
    private int _sampleCount = 0;

    // Wykres
    private const int MaxVisiblePoints = 400; // Okno czasowe 2 sekundy przy 200Hz
    public object SyncItem { get; } = new object();
    public ObservableCollection<double> XValues { get; set; } = new();
    public ObservableCollection<double> YValues { get; set; } = new();
    public ObservableCollection<double> ZValues { get; set; } = new();
    public ISeries[] ImuSeries { get; set; }

    public MainPage()
    {
        InitializeComponent();

        _adapter = CrossBluetoothLE.Current.Adapter;
        InitCsvBuffer();

        // Konfiguracja wykresu z wyłączoną animacją i bez kropiek (GeometrySize = 0) dla wydajności
        ImuSeries = new ISeries[]
        {
            new LineSeries<double>
            {
                Values = XValues,
                Name = "X",
                Fill = null,
                GeometrySize = 0,
                Stroke = new SolidColorPaint(SKColors.Red) { StrokeThickness = 2 },
                EnableNullSplitting = false
            },
            new LineSeries<double>
            {
                Values = YValues,
                Name = "Y",
                Fill = null,
                GeometrySize = 0,
                Stroke = new SolidColorPaint(SKColors.Green) { StrokeThickness = 2 },
                EnableNullSplitting = false
            },
            new LineSeries<double>
            {
                Values = ZValues,
                Name = "Z",
                Fill = null,
                GeometrySize = 0,
                Stroke = new SolidColorPaint(SKColors.Blue) { StrokeThickness = 2 },
                EnableNullSplitting = false
            }
        };

        BindingContext = this;
    }

    private void InitCsvBuffer()
    {
        _csvData = new StringBuilder();
        _csvData.AppendLine("X,Y,Z");
    }

    private async void OnConnectToggleClicked(object sender, EventArgs e)
    {
        BtnConnect.IsEnabled = false;

        try
        {
            if (!_isConnected)
            {
                var btStatus = await Permissions.CheckStatusAsync<Permissions.Bluetooth>();
                if (btStatus != PermissionStatus.Granted)
                {
                    btStatus = await Permissions.RequestAsync<Permissions.Bluetooth>();
                    if (btStatus != PermissionStatus.Granted) return;
                }

                var locStatus = await Permissions.CheckStatusAsync<Permissions.LocationWhenInUse>();
                if (locStatus != PermissionStatus.Granted)
                {
                    locStatus = await Permissions.RequestAsync<Permissions.LocationWhenInUse>();
                    if (locStatus != PermissionStatus.Granted) return;
                }

                LblStatus.Text = "Status: Scanning...";
                _adapter.DeviceDiscovered += OnDeviceDiscovered;

                await _adapter.StartScanningForDevicesAsync(new[] { _serviceId });
            }
            else
            {
                await DisconnectDeviceAsync();

                _isConnected = false;
                LblStatus.Text = "Status: Disconnected";
                BtnConnect.Text = "Connect to M5Stick";
                BtnSave.IsEnabled = false;
            }
        }
        catch (Exception ex)
        {
            LblStatus.Text = $"Error: {ex.Message}";
        }
        finally
        {
            BtnConnect.IsEnabled = true;
        }
    }

    private async void OnDeviceDiscovered(object sender, DeviceEventArgs e)
    {
        await _adapter.StopScanningForDevicesAsync();
        _adapter.DeviceDiscovered -= OnDeviceDiscovered;

        _m5StickDevice = e.Device;

        MainThread.BeginInvokeOnMainThread(() => LblStatus.Text = "Status: Connecting...");

        try
        {
            await _adapter.ConnectToDeviceAsync(_m5StickDevice);
            await _m5StickDevice.RequestMtuAsync(125);

            var service = await _m5StickDevice.GetServiceAsync(_serviceId);
            _imuCharacteristic = await service.GetCharacteristicAsync(_characteristicId);

            _imuCharacteristic.ValueUpdated += OnCharacteristicValueUpdated;
            await _imuCharacteristic.StartUpdatesAsync();

            MainThread.BeginInvokeOnMainThread(() =>
            {
                _isConnected = true;
                LblStatus.Text = "Status: Connected";
                BtnConnect.Text = "Disconnect";
                BtnSave.IsEnabled = true;
            });
        }
        catch (Exception ex)
        {
            MainThread.BeginInvokeOnMainThread(() => LblStatus.Text = $"Connection Error: {ex.Message}");
        }
    }

    private void OnCharacteristicValueUpdated(object sender, CharacteristicUpdatedEventArgs e)
    {
        var data = e.Characteristic.Value;

        if (data != null && data.Length == 120)
        {
            // Parsowanie 10 próbek z pakietu BLE
            var xBatch = new double[10];
            var yBatch = new double[10];
            var zBatch = new double[10];

            for (int i = 0; i < 10; i++)
            {
                int offset = i * 12;
                xBatch[i] = BitConverter.ToSingle(data, offset);
                yBatch[i] = BitConverter.ToSingle(data, offset + 4);
                zBatch[i] = BitConverter.ToSingle(data, offset + 8);
            }

            // Aktualizacja UI i kolekcji pod spodem
            MainThread.BeginInvokeOnMainThread(() =>
            {
                lock (SyncItem)
                {
                    for (int i = 0; i < 10; i++)
                    {
                        XValues.Add(xBatch[i]);
                        YValues.Add(yBatch[i]);
                        ZValues.Add(zBatch[i]);

                        _csvData.AppendLine(string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F4},{1:F4},{2:F4}", xBatch[i], yBatch[i], zBatch[i]));
                        _sampleCount++;

                        if (XValues.Count > MaxVisiblePoints)
                        {
                            XValues.RemoveAt(0);
                            YValues.RemoveAt(0);
                            ZValues.RemoveAt(0);
                        }
                    }
                }

                LblCounter.Text = $"Collected samples: {_sampleCount}";
            });
        }
    }

    private async Task DisconnectDeviceAsync()
    {
        if (_m5StickDevice != null)
        {
            if (_imuCharacteristic != null)
            {
                _imuCharacteristic.ValueUpdated -= OnCharacteristicValueUpdated;
                await _imuCharacteristic.StopUpdatesAsync();
            }
            await _adapter.DisconnectDeviceAsync(_m5StickDevice);
        }
    }

    private void OnResetButtonClicked(object sender, EventArgs e)
    {
        lock (SyncItem)
        {
            XValues.Clear();
            YValues.Clear();
            ZValues.Clear();

            _sampleCount = 0;
            InitCsvBuffer();
        }

        LblCounter.Text = $"Collected samples: {_sampleCount}";
    }

    private async void OnSaveClicked(object sender, EventArgs e)
    {
        try
        {
            string fileName = $"imu_data_{DateTimeOffset.UtcNow.ToUnixTimeSeconds()}.csv";
            string filePath = Path.Combine(FileSystem.CacheDirectory, fileName);

            File.WriteAllText(filePath, _csvData.ToString());

            await Share.Default.RequestAsync(new ShareFileRequest
            {
                Title = "Save to CSV",
                File = new ShareFile(filePath)
            });
        }
        catch (Exception ex)
        {
            LblStatus.Text = $"Save Error: {ex.Message}";
        }
    }
}