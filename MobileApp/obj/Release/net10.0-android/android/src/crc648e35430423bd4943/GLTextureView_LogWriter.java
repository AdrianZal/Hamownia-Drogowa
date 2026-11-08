package crc648e35430423bd4943;


public class GLTextureView_LogWriter
	extends java.io.Writer
	implements
		mono.android.IGCUserPeer
{

	public GLTextureView_LogWriter ()
	{
		super ();
		if (getClass () == GLTextureView_LogWriter.class) {
			mono.android.TypeManager.Activate ("SkiaSharp.Views.Android.GLTextureView+LogWriter, SkiaSharp.Views.Android", "", this, new java.lang.Object[] {  });
		}
	}

	public void close ()
	{
		n_close ();
	}

	private native void n_close ();

	public void flush ()
	{
		n_flush ();
	}

	private native void n_flush ();

	public void write (char[] p0, int p1, int p2)
	{
		n_write (p0, p1, p2);
	}

	private native void n_write (char[] p0, int p1, int p2);

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
