import { Link } from 'react-router-dom'

export function BitcoinUnavailable() {
  return (
    <section className="mx-auto max-w-xl space-y-3 rounded-lg border border-border bg-surface p-6" aria-label="Bitcoin no disponible">
      <h1 className="text-xl font-semibold">Bitcoin no está incluido en este servidor</h1>
      <p className="text-sm">El análisis de Bitcoin vive en la rama <code>feature/btc-engine-v0</code>, que todavía no se ha fusionado con esta versión. Para usarlo, lanza PITQuant desde esa rama (su carpeta de trabajo) y abre <code>/bitcoin</code>.</p>
      <p className="text-sm text-muted">Mientras tanto puedes usar <Link className="text-accent underline" to="/">Acciones</Link> o <Link className="text-accent underline" to="/simulations">Simulation Lab</Link>. La <Link className="text-accent underline" to="/ayuda#bitcoin">guía</Link> explica cómo funciona.</p>
    </section>
  )
}
