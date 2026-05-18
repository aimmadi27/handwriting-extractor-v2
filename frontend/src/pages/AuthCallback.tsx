import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // Token is passed in the URL fragment (#) — fragments are never sent to
    // servers or logged by proxies, unlike query parameters.
    const token = window.location.hash.slice(1);
    if (token) {
      localStorage.setItem('token', token);
      navigate('/app', { replace: true });
    } else {
      navigate('/', { replace: true });
    }
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
