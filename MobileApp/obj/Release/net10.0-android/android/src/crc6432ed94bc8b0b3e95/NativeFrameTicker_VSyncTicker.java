package crc6432ed94bc8b0b3e95;


public class NativeFrameTicker_VSyncTicker
	extends java.lang.Object
	implements
		mono.android.IGCUserPeer,
		android.view.Choreographer.FrameCallback
{

	public NativeFrameTicker_VSyncTicker ()
	{
		super ();
		if (getClass () == NativeFrameTicker_VSyncTicker.class) {
			mono.android.TypeManager.Activate ("LiveChartsCore.Native.NativeFrameTicker+VSyncTicker, LiveChartsCore.SkiaSharpView.Maui", "", this, new java.lang.Object[] {  });
		}
	}

	public void doFrame (long p0)
	{
		n_doFrame (p0);
	}

	private native void n_doFrame (long p0);

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
