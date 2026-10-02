import { useEffect, useState } from 'react'

export function useTheme() {
  const [dark, setDark] = useState(() => (localStorage.getItem('pq-theme') ?? 'dark') === 'dark')
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('pq-theme', dark ? 'dark' : 'light')
  }, [dark])
  return { dark, toggle: () => setDark((d) => !d) }
}
