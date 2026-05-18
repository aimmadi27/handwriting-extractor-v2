import { useState, useEffect } from 'react';
import { fetchMe, logoutUser } from '../api/client';

export interface AuthUser {
  email: string;
  name: string;
  picture?: string;
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Session is determined entirely by the httpOnly cookie — no localStorage.
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await logoutUser();
    setUser(null);
    window.location.href = '/';
  }

  return { user, loading, logout };
}
