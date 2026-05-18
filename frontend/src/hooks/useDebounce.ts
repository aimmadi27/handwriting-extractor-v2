import { useEffect, useRef } from 'react';

export function useDebounce<T>(value: T, delay: number, callback: (v: T) => void): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    const id = setTimeout(() => callbackRef.current(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
}
