import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');

    if (!code) {
      navigate('/', { replace: true });
      return;
    }

    // Exchange the one-time code for httpOnly access + refresh cookies.
    // The JWT is set as a cookie by the server — it never touches JS storage.
    fetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ code }),
    })
      .then((res) => {
        if (res.ok) navigate('/app', { replace: true });
        else navigate('/', { replace: true });
      })
      .catch(() => navigate('/', { replace: true }));
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="flex flex-col items-center gap-4 text-white">
        <div className="w-10 h-10 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400">Signing you in…</p>
      </div>
    </div>
  );
}
