package crc640d7c6d57b8a5f296;


public class Adapter_Api18BleScanCallback
	extends java.lang.Object
	implements
		mono.android.IGCUserPeer,
		android.bluetooth.BluetoothAdapter.LeScanCallback
{

	public Adapter_Api18BleScanCallback ()
	{
		super ();
		if (getClass () == Adapter_Api18BleScanCallback.class) {
			mono.android.TypeManager.Activate ("Plugin.BLE.Android.Adapter+Api18BleScanCallback, Plugin.BLE", "", this, new java.lang.Object[] {  });
		}
	}

	public void onLeScan (android.bluetooth.BluetoothDevice p0, int p1, byte[] p2)
	{
		n_onLeScan (p0, p1, p2);
	}

	private native void n_onLeScan (android.bluetooth.BluetoothDevice p0, int p1, byte[] p2);

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
