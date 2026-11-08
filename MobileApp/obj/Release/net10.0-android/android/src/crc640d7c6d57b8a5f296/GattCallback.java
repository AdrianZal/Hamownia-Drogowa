package crc640d7c6d57b8a5f296;


public class GattCallback
	extends android.bluetooth.BluetoothGattCallback
	implements
		mono.android.IGCUserPeer
{

	public GattCallback ()
	{
		super ();
		if (getClass () == GattCallback.class) {
			mono.android.TypeManager.Activate ("Plugin.BLE.Android.GattCallback, Plugin.BLE", "", this, new java.lang.Object[] {  });
		}
	}

	public void onConnectionStateChange (android.bluetooth.BluetoothGatt p0, int p1, int p2)
	{
		n_onConnectionStateChange (p0, p1, p2);
	}

	private native void n_onConnectionStateChange (android.bluetooth.BluetoothGatt p0, int p1, int p2);

	public void onServicesDiscovered (android.bluetooth.BluetoothGatt p0, int p1)
	{
		n_onServicesDiscovered (p0, p1);
	}

	private native void n_onServicesDiscovered (android.bluetooth.BluetoothGatt p0, int p1);

	public void onCharacteristicRead (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1, int p2)
	{
		n_onCharacteristicRead (p0, p1, p2);
	}

	private native void n_onCharacteristicRead (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1, int p2);

	public void onCharacteristicChanged (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1)
	{
		n_onCharacteristicChanged (p0, p1);
	}

	private native void n_onCharacteristicChanged (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1);

	public void onCharacteristicWrite (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1, int p2)
	{
		n_onCharacteristicWrite (p0, p1, p2);
	}

	private native void n_onCharacteristicWrite (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattCharacteristic p1, int p2);

	public void onReliableWriteCompleted (android.bluetooth.BluetoothGatt p0, int p1)
	{
		n_onReliableWriteCompleted (p0, p1);
	}

	private native void n_onReliableWriteCompleted (android.bluetooth.BluetoothGatt p0, int p1);

	public void onMtuChanged (android.bluetooth.BluetoothGatt p0, int p1, int p2)
	{
		n_onMtuChanged (p0, p1, p2);
	}

	private native void n_onMtuChanged (android.bluetooth.BluetoothGatt p0, int p1, int p2);

	public void onReadRemoteRssi (android.bluetooth.BluetoothGatt p0, int p1, int p2)
	{
		n_onReadRemoteRssi (p0, p1, p2);
	}

	private native void n_onReadRemoteRssi (android.bluetooth.BluetoothGatt p0, int p1, int p2);

	public void onDescriptorWrite (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattDescriptor p1, int p2)
	{
		n_onDescriptorWrite (p0, p1, p2);
	}

	private native void n_onDescriptorWrite (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattDescriptor p1, int p2);

	public void onDescriptorRead (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattDescriptor p1, int p2)
	{
		n_onDescriptorRead (p0, p1, p2);
	}

	private native void n_onDescriptorRead (android.bluetooth.BluetoothGatt p0, android.bluetooth.BluetoothGattDescriptor p1, int p2);

	private java.util.ArrayList refList;
	public void monodroidAddReference (java.lang.Object obj)
	{
		if (refList == null)
			refList = new java.util.ArrayList ();
		refList.add (obj);
	}

	public void monodroidClearReferences ()
	{
		if (refList != null)
			refList.clear ();
	}
}
