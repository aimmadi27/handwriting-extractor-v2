import { useState, useEffect } from 'react';
import { fetchMe } from '../api/client';

export interface AuthUser {
  email: string;
  name: string;
  picture?: string;
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false));
  }, []);

  function logout() {
    localStorage.removeItem('token');
    setUser(null);
  }

  return { user, loading, logout };
}
