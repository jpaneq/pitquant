import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardBody, CardHeader } from '../../components/ui/primitives'
import { GLOSSARY } from '../../lib/glossary'
import { ChartAnatomy, DailyRoutine, QuoteVsModelBar, SimStates, TradePlanDiagram, WalkForward } from './diagrams'

export const SECTIONS = [
  ['empezar', 'Empezar'],
  ['acciones', 'Acciones (Analyzer)'],
  ['senales', 'Señales R y pruebas F en el gráfico'],
  ['plan', 'Plan de operación'],
  ['simulation', 'Simulation Lab'],
  ['diaria', 'Pruebas diarias'],
  ['bitcoin', 'Bitcoin'],
  ['research', 'Research Lab'],
  ['estado', 'Estado de datos y ajustes'],
  ['glosario', 'Glosario'],
  ['avisos', 'Avisos importantes'],
] as const

const H = ({ id, children }: { id: string; children: React.ReactNode }) => <h2 id={id} className="scroll-mt-4 border-b border-border pb-1 text-lg font-semibold">{children}</h2>
const P = ({ children }: { children: React.ReactNode }) => <p className="my-2 text-sm leading-relaxed">{children}</p>
const Ul = ({ children }: { children: React.ReactNode }) => <ul className="my-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">{children}</ul>

export function HelpPage() {
  const [q, setQ] = useState('')
  const terms = useMemo(() => Object.entries(GLOSSARY).filter(([, v], i, a) => a.findIndex(([, w]) => w.t === v.t) === i).filter(([k, v]) => !q || `${k} ${v.t} ${v.q}`.toLowerCase().includes(q.toLowerCase())).sort((a, b) => a[1].t.localeCompare(b[1].t)), [q])
  return (
    <div className="mx-auto flex max-w-5xl gap-6">
      <nav aria-label="Índice de la guía" className="sticky top-0 hidden h-fit w-52 shrink-0 text-sm lg:block">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Índice</div>
        <ol className="space-y-1">{SECTIONS.map(([id, t]) => <li key={id}><a className="text-muted hover:text-accent" href={`#${id}`}>{t}</a></li>)}</ol>
      </nav>
      <article className="min-w-0 flex-1 space-y-4">
        <header>
          <h1 className="text-2xl font-semibold">Guía de uso de PITQuant</h1>
          <P>Esta guía explica cada programa con ejemplos. Todas las ilustraciones son esquemas con datos inventados para enseñar; no son precios reales. En cualquier pantalla verás pequeñas <b>«i»</b> junto a cada magnitud: púlsalas para ver qué es y cuándo es buena o mala señal.</P>
          <details className="rounded border border-border p-2 text-xs lg:hidden"><summary>Índice</summary><ol className="mt-1 space-y-1">{SECTIONS.map(([id, t]) => <li key={id}><a className="text-accent" href={`#${id}`}>{t}</a></li>)}</ol></details>
        </header>

        <H id="empezar">Empezar</H>
        <P>PITQuant es una plataforma de análisis bursátil <b>point-in-time</b>: cada dato lleva la fecha en que un inversor pudo conocerlo, así se evita «mirar el futuro» sin querer. Sirve para estudiar, probar ideas con dinero simulado y comprobar con honestidad si funcionan. <b>No ejecuta órdenes reales ni da consejo de inversión.</b></P>
        <Ul>
          <li><b>Aplicaciones:</b> el botón <b>Aplicaciones</b> de la barra superior abre Acciones, Bitcoin o Simulation Lab desde cualquier pantalla.</li>
          <li><b>Buscar:</b> el cuadro superior acepta ticker, nombre, CUSIP o ISIN (p. ej. AAPL, Apple).</li>
          <li><b>Ayuda:</b> el botón <b>Ayuda</b> de la barra superior te trae aquí.</li>
        </Ul>

        <H id="acciones">Acciones (Analyzer)</H>
        <ChartAnatomy />
        <Ul>
          <li><b>Cabecera:</b> último cierre disponible y su variación. Si ves <i>STALE</i>, faltan sesiones: el dato no es de hoy.</li>
          <li><b>Gráfico:</b> velas, volumen y capas activables (medias, Bollinger, soportes/resistencias, RSI, MACD). Rangos de 1M a MAX. Precios ajustados por splits.</li>
          <li><b>Tarjetas:</b> Fundamentales (SEC), Técnicos, Valoración, Análisis y Plan de operación. Cada cifra tiene su «i».</li>
          <li><b>Predicción:</b> hoy dice «not yet validated»: no existe un modelo validado y por eso no se muestra ninguna probabilidad. Es intencionado.</li>
          <li><b>Informe:</b> el botón de informe descarga un resumen JSON o Markdown.</li>
        </Ul>
        <P><b>Ejemplo:</b> abre <Link className="text-accent underline" to="/analyzer/AAPL">AAPL</Link>, pulsa la «i» de «ROE» y verás qué es, cuándo es positivo (alto con poca deuda) y cuándo negativo.</P>

        <H id="senales">Señales R y pruebas F en el gráfico</H>
        <P>En la barra del gráfico hay dos botones:</P>
        <Ul>
          <li><b>Señales algoritmo (R)</b>, flechas: lo que habría hecho la regla del plan en fechas pasadas usando solo los datos conocidos entonces. Es <b>retrospectivo</b>, sin comisiones, no validado y no guarda nada. Con menos de 10 operaciones cerradas no se muestra ninguna tasa de aciertos: sería ruido.</li>
          <li><b>Mis pruebas (F)</b>, círculos: tus simulaciones paper reales de ese valor.</li>
        </Ul>
        <P>El periodo reservado (holdout) nunca se dibuja. Debajo del gráfico verás un resumen y una tabla de operaciones con entrada, salida, resultado y múltiplo de riesgo (R).</P>

        <H id="plan">Plan de operación</H>
        <TradePlanDiagram />
        <Ul>
          <li><b>Zona de entrada:</b> donde el plan compraría. Si el precio no llega, no hay operación.</li>
          <li><b>Stop:</b> donde sale para limitar la pérdida. 1R = distancia entrada-stop.</li>
          <li><b>Objetivos:</b> TP1 (1,5R o la siguiente resistencia) y TP2 (3R).</li>
          <li><b>Tamaño:</b> indica capital y % de riesgo; calcula cuántas acciones comprar arriesgando solo eso.</li>
        </Ul>
        <P>Es un escenario por reglas, <b>no validado con backtest</b>: no garantiza nada.</P>

        <H id="simulation">Simulation Lab</H>
        <SimStates />
        <Ul>
          <li><b>Crear:</b> en el Analyzer pulsa <b>Simulate trade</b>; elige el plan (el de PITQuant, uno modificado o uno propio), capital y riesgo.</li>
          <li><b>Seguimiento:</b> la operación se evalúa con cada nueva vela diaria cerrada. Todo queda en una cronología que no se reescribe.</li>
          <li><b>Resultado:</b> retorno, R, caída máxima, mejor y peor momento (MFE/MAE) y comparación con el índice.</li>
          <li><b>Post-mortem e Insights:</b> clasifica por qué salió así y mira estadísticas agregadas; con menos de 10 operaciones por segmento no hay conclusiones.</li>
          <li><b>Comparar planes:</b> «Mismas barras, dos planes» enseña qué habría pasado con otro plan (contrafactual, no es real).</li>
        </Ul>
        <P>Abre <Link className="text-accent underline" to="/simulations">Simulation Lab</Link>. Es dinero simulado: no hay broker.</P>

        <H id="diaria">Pruebas diarias</H>
        <DailyRoutine />
        <P>Una rutina lanza cada día el plan de reglas sobre varios valores y abre operaciones paper para los que lo cumplen. Se ejecuta desde el terminal:</P>
        <pre className="overflow-auto rounded bg-surface-2 p-3 text-xs">python -m pitquant.cli strategy-daily-test --refresh --json</pre>
        <P>Es idempotente: ejecutarla dos veces el mismo día no duplica. Los resultados salen con avisos como <i>INSUFFICIENT_SAMPLE</i> (muestra pequeña) y <i>COSTS_NOT_MODELED</i> (sin comisiones). Las estrategias basadas en predicción están deshabilitadas hasta que exista un modelo validado.</P>

        <H id="bitcoin">Bitcoin</H>
        <QuoteVsModelBar />
        <Ul>
          <li><b>Cotización en vivo</b> (Binance Spot, BTC/USDT): se refresca cada 5 s con insignia LIVE / RECENT / STALE. Solo es de pantalla.</li>
          <li><b>MODEL BAR 1D UTC:</b> la última vela diaria cerrada; es la única que usan las predicciones.</li>
          <li><b>Seguimiento de predicciones:</b> cada predicción se comprueba sola al vencer su horizonte (7, 30, 90, 180 o 365 días). Hasta entonces aparece «Pendiente» con la fecha de madurez.</li>
          <li><b>Simulaciones BTC:</b> operaciones paper con importe fraccionario.</li>
        </Ul>
        <P>Ábrelo desde <Link className="text-accent underline" to="/bitcoin">Bitcoin</Link> (también en el menú Aplicaciones).</P>

        <H id="research">Research Lab</H>
        <WalkForward />
        <Ul>
          <li><b>Puertas de datos:</b> condiciones que deben cumplirse antes de entrenar. Cerradas = no se entrena nada.</li>
          <li><b>Holdout sellado:</b> oct-2022 → sep-2025, reservado para una evaluación final única de un modelo congelado.</li>
          <li><b>Validación walk-forward:</b> el modelo siempre se prueba en fechas posteriores a las de entrenamiento, con purga y embargo para que no se contagien.</li>
        </Ul>

        <H id="estado">Estado de datos y ajustes</H>
        <P><b>Data Status</b> muestra proveedores configurados, versiones de motor y avisos de calidad. Las claves de proveedores se leen del entorno y nunca se muestran. Con el token público de demostración solo hay precios de AAPL, MSFT y VTI.</P>

        <H id="glosario">Glosario</H>
        <input aria-label="Buscar en el glosario" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar término…" className="w-full rounded border border-border bg-surface px-3 py-2 text-sm" />
        <Card>
          <CardHeader title="Términos" sub={`${terms.length} entradas`} />
          <CardBody className="space-y-3">
            {terms.map(([k, v]) => (
              <div key={k} className="text-sm">
                <b>{v.t}</b> <span className="text-muted">— {v.q}</span>
                {v.p ? <div className="text-up text-xs"><b>Positivo:</b> {v.p}</div> : null}
                {v.n ? <div className="text-down text-xs"><b>Negativo:</b> {v.n}</div> : null}
                {v.c ? <div className="text-xs text-muted"><b>Ojo:</b> {v.c}</div> : null}
              </div>
            ))}
          </CardBody>
        </Card>

        <H id="avisos">Avisos importantes</H>
        <Ul>
          <li>Nada de esto es consejo de inversión. Las cifras son descriptivas.</li>
          <li>«Retrospectivo» significa que se recalcula el pasado con datos descargados hoy: sirve para entender, no para demostrar.</li>
          <li>Una tasa de aciertos con pocas operaciones es ruido: espera a tener muestra suficiente.</li>
          <li>Ningún modelo predictivo está validado todavía; el sistema no inventa probabilidades.</li>
        </Ul>
      </article>
    </div>
  )
}
