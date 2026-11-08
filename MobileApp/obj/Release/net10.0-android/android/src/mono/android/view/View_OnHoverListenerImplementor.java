package mono.android.view;


public class View_OnHoverListenerImplementor
	extends java.lang.Object
	implements
		mono.android.IGCUserPeer,
		android.view.View.OnHoverListener
{

	public View_OnHoverListenerImplementor ()
	{
		super ();
		if (getClass () == View_OnHoverListenerImplementor.class) {
			mono.android.TypeManager.Activate ("Android.Views.View+IOnHoverListenerImplementor, Mono.Android", "", this, new java.lang.Object[] {  });
		}
	}

	public boolean onHover (android.view.View p0, android.view.MotionEvent p1)
	{
		return n_onHover (p0, p1);
	}

	private native boolean n_onHover (android.view.View p0, android.view.MotionEvent p1);

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
