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
  ['posiciones', 'Compras simuladas: ampliar, mantener o vender'],
  ['simulation', 'Simulation Lab'],
  ['diaria', 'Pruebas diarias'],
  ['rutina', 'Rutina diaria de compras simuladas'],
  ['backtest', 'Backtest histórico: ¿acertaba la regla?'],
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

        <H id="plan">Plan de operación (trade plan)</H>
        <P><b>Qué es:</b> una receta escrita de antemano para una operación: <i>dónde entro, dónde salgo si me equivoco y dónde recojo beneficios</i>. Decidirlo antes evita decidir con miedo o euforia cuando el precio ya se mueve. Está disponible para <b>acciones</b> (en el Analyzer, justo bajo el gráfico) y para <b>Bitcoin</b> (pestaña Analyzer de Bitcoin, calculado con la última vela diaria cerrada).</P>
        <TradePlanDiagram />
        <Ul>
          <li><b>Zona de entrada:</b> donde el plan compraría. Si el precio no llega, no hay operación.</li>
          <li><b>Stop:</b> donde sale para limitar la pérdida. 1R = distancia entrada-stop.</li>
          <li><b>Objetivos:</b> TP1 (1,5R o la siguiente resistencia) y TP2 (3R).</li>
          <li><b>Tamaño:</b> indica capital y % de riesgo; calcula cuántas acciones comprar arriesgando solo eso.</li>
        </Ul>
        <P>Es un escenario por reglas, <b>no validado con backtest</b>: no garantiza nada.</P>

        <H id="posiciones">Compras simuladas: ampliar, mantener o vender</H>
        <P>Bajo el plan de operación (acciones) y en la pestaña Analyzer de Bitcoin hay <b>Mis compras simuladas</b>. Eliges un importe y un <b>horizonte en meses</b> (y, si quieres, un objetivo de rentabilidad). El algoritmo revisa la posición con reglas visibles y responde:</P>
        <Ul>
          <li><b>AMPLIAR</b>: la puntuación es alta (≥ +2,5), la tendencia es alcista, el precio no está estirado y queda plazo.</li>
          <li><b>MANTENER</b>: ninguna regla pide actuar, o hay señal favorable pero algo lo impide (se explica qué).</li>
          <li><b>VENDER</b>: se toca tu stop, se cumple el objetivo con señal ya débil, vence el horizonte sin respaldo de las reglas, o la puntuación es muy negativa (≤ −2).</li>
        </Ul>
        <P><b>El horizonte cambia el peso de las reglas:</b> a 1-3 meses mandan la tendencia y el soporte del precio; a 4-8 meses pesan igual la tendencia, la media de 200 y el momentum; a 9 meses o más mandan la tendencia larga, la valoración y los fundamentales (en Bitcoin no hay valoración ni fundamentales, esas reglas se saltan y se indica). Puedes <b>ampliar</b>, <b>vender parte</b> o <b>cerrar</b> en simulado y guardar cada revisión.</P>
        <P><b>Límites:</b> son reglas descriptivas con pesos sin validar, no una predicción ni consejo de inversión. La misma posición puede cambiar de «mantener» a «vender» si cambias el plazo.</P>

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

        <H id="rutina">Rutina diaria de compras simuladas</H>
        <P>Cada día el programa analiza <b>una empresa del IBEX, una del S&amp;P 500, una del MSCI World y Bitcoin</b> (rotación automática entre las que tienen datos). Para cada horizonte —<b>1, 3, 6, 12 y 24 meses</b>— decide con las reglas si abre una compra simulada y, si lo hace, fija:</P>
        <Ul>
          <li><b>Precio de entrada</b>: el precio del momento.</li>
          <li><b>Precio objetivo</b>: entrada × (1 + 0,5 · volatilidad anual · √(meses/12)), con un mínimo del 2 %.</li>
          <li><b>Stop</b>: el mayor entre 2 ATR y 0,35 · volatilidad · √(meses/12).</li>
        </Ul>
        <P><b>Cada semana</b> se evalúa cada predicción abierta con las velas diarias posteriores a la entrada: objetivo cumplido, stop, o vencida al terminar el plazo (si ambos se tocan el mismo día se cuenta como stop). El informe en <b>texto plano</b> (menú Rutina diaria → Copiar informe) lista parámetros, actividad, datos no accesibles, resultados y puntos a revisar: pásamelo para reajustar lo que no se cumpla.</P>
        <P><b>No comprar también cuenta:</b> cada «no compra» se valora igual, como si se hubiera comprado con el mismo objetivo y stop: acierta si el objetivo no se habría cumplido; es una oportunidad perdida si sí. <b>Horario:</b> la ejecución programada solo analiza los mercados abiertos en ese momento (Madrid, Nueva York; Bitcoin siempre).</P>
        <P><b>De dónde salen los precios:</b> Bitcoin, de Binance (público). Las acciones, de Yahoo Finance (gratuito, sin clave, no oficial: puede fallar o cambiar y es solo para esta simulación), salvo AAPL y MSFT que ya tienen datos de otra fuente; si defines <code>PITQUANT_EODHD_API_KEY</code> se usará esa. <code>routine-run --refresh</code> da de alta y descarga todos los valores de la lista. No es tiempo real: el precio de decisión es el último cierre diario (STALE si falta alguna sesión).</P>

        <H id="backtest">Backtest histórico: ¿acertaba la regla?</H>
        <P>Para saber si el algoritmo acierta en <b>subida y bajada</b> no hace falta esperar meses: el backtest rehace el pasado. En cada fecha (una al mes desde 2012) la regla ve <b>solo lo que se sabía entonces</b> y emite una previsión por horizonte: <b>SUBE</b>, <b>BAJA</b> o <b>NEUTRAL</b>. Después se mira qué hizo el precio y se compara con la <b>tasa base</b> (cuántas veces sube un valor cualquiera en ese plazo): lo que importa es la <i>ventaja</i> sobre esa base. Se genera con <code>python -m pitquant.cli backtest-run</code> y aparece en la página Rutina diaria.</P>
        <Ul>
          <li><b>Holdout intacto:</b> el periodo oct-2022 → sep-2025 nunca se usa.</li>
          <li><b>No busca valores exactos:</b> mira tendencias (¿subió o bajó?) y si se cumplió el objetivo o el stop.</li>
          <li><b>Cuidado:</b> lista de empresas actuales (sesgo de supervivencia), fuente gratuita no oficial, ventanas solapadas (la muestra efectiva es menor que N) y sin costes. Con N pequeño no se muestran porcentajes.</li>
        </Ul>
        <P><b>Programar las pruebas:</b> doble clic en <code>Instalar_rutina_diaria.command</code> (lunes a viernes 09:30 y 16:00, hora de Madrid; cada ejecución analiza solo las bolsas abiertas). Para quitarla, el mismo archivo con el argumento <code>desinstalar</code>.</P>

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
