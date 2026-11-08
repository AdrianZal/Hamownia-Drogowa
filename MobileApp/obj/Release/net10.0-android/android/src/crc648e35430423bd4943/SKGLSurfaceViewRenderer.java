package crc648e35430423bd4943;


public abstract class SKGLSurfaceViewRenderer
	extends java.lang.Object
	implements
		mono.android.IGCUserPeer,
		android.opengl.GLSurfaceView.Renderer
{

	public SKGLSurfaceViewRenderer ()
	{
		super ();
		if (getClass () == SKGLSurfaceViewRenderer.class) {
			mono.android.TypeManager.Activate ("SkiaSharp.Views.Android.SKGLSurfaceViewRenderer, SkiaSharp.Views.Android", "", this, new java.lang.Object[] {  });
		}
	}

	public void onDrawFrame (javax.microedition.khronos.opengles.GL10 p0)
	{
		n_onDrawFrame (p0);
	}

	private native void n_onDrawFrame (javax.microedition.khronos.opengles.GL10 p0);

	public void onSurfaceChanged (javax.microedition.khronos.opengles.GL10 p0, int p1, int p2)
	{
		n_onSurfaceChanged (p0, p1, p2);
	}

	private native void n_onSurfaceChanged (javax.microedition.khronos.opengles.GL10 p0, int p1, int p2);

	public void onSurfaceCreated (javax.microedition.khronos.opengles.GL10 p0, javax.microedition.khronos.egl.EGLConfig p1)
	{
		n_onSurfaceCreated (p0, p1);
	}

	private native void n_onSurfaceCreated (javax.microedition.khronos.opengles.GL10 p0, javax.microedition.khronos.egl.EGLConfig p1);

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
