// Ilustraciones de la guía: esquemas SVG con datos de ejemplo (NO son datos de mercado).
const W = 'currentColor'
const up = 'var(--up, #12805c)', down = 'var(--down, #c0392b)', accent = 'var(--accent, #4f6ef7)', warn = 'var(--warn, #b7791f)'

function Frame({ label, children, h = 190 }: { label: string; children: React.ReactNode; h?: number }) {
  return (
    <figure className="my-3 rounded-lg border border-border bg-surface-2 p-3">
      <svg role="img" aria-label={label} viewBox={`0 0 560 ${h}`} className="w-full text-fg" fontFamily="Inter, system-ui, sans-serif" fontSize="11">{children}</svg>
      <figcaption className="mt-1 text-center text-[11px] text-muted">{label} · ejemplo ilustrativo, no son datos reales</figcaption>
    </figure>
  )
}
const Candle = ({ x, o, c, h, l }: { x: number; o: number; c: number; h: number; l: number }) => {
  const col = c >= o ? up : down
  return <g><line x1={x} x2={x} y1={h} y2={l} stroke={col} /><rect x={x - 4} width="8" y={Math.min(o, c)} height={Math.max(Math.abs(c - o), 1.5)} fill={col} /></g>
}

export function ChartAnatomy() {
  const cs = [[120, 112, 108, 124], [112, 104, 100, 116], [104, 108, 98, 112], [108, 98, 94, 112], [98, 90, 86, 102], [90, 96, 84, 100], [96, 84, 80, 100], [84, 76, 72, 90], [76, 82, 70, 86], [82, 70, 66, 86], [70, 62, 58, 74], [62, 66, 56, 70]]
  return (
    <Frame label="Anatomía del gráfico del Analyzer" h={210}>
      <polyline fill="none" stroke={accent} strokeWidth="1.5" strokeDasharray="4 3" points="40,120 110,112 180,104 250,96 320,90 390,84 460,78 530,70" />
      {cs.map(([o, c, l, h], i) => <Candle key={i} x={60 + i * 38} o={o} c={c} l={l} h={h} />)}
      <text x="536" y="64" fill={accent} fontSize="10">SMA50</text>
      <path d="M142 150 l-6 10 h12z" fill={accent} /><text x="104" y="176" fill={accent}>R · entry</text>
      <path d="M404 40 l-6 -10 h12z" fill={up} /><text x="388" y="26" fill={up}>R · tp</text>
      <circle cx="218" cy="170" r="6" fill={warn} /><text x="190" y="190" fill={warn}>F · plan (tu prueba)</text>
      <line x1="40" x2="540" y1="150" y2="150" stroke={down} strokeDasharray="2 4" /><text x="44" y="146" fill={down}>stop</text>
    </Frame>
  )
}

export function TradePlanDiagram() {
  return (
    <Frame label="Plan de operación: entrada, stop y objetivos" h={200}>
      {[['TP2 · 3R', 30, up], ['TP1 · 1,5R', 70, up]].map(([t, y, c]) => <g key={String(t)}><line x1="150" x2="520" y1={Number(y)} y2={Number(y)} stroke={String(c)} strokeDasharray="5 4" /><text x="20" y={Number(y) + 4} fill={String(c)}>{String(t)}</text></g>)}
      <rect x="150" y="100" width="370" height="22" fill={accent} opacity="0.2" /><text x="20" y="115" fill={accent}>Zona de entrada</text>
      <line x1="150" x2="520" y1="160" y2="160" stroke={down} strokeWidth="2" /><text x="20" y="164" fill={down}>Stop</text>
      <line x1="560" x2="560" y1="111" y2="160" stroke={W} /><text x="470" y="140" fontSize="10">1R = riesgo</text>
      <polyline fill="none" stroke={W} strokeWidth="1.5" points="150,60 220,80 290,100 340,112 400,90 460,60 510,34" />
    </Frame>
  )
}

export function SimStates() {
  const box = (x: number, y: number, t: string, c = W) => <g key={t}><rect x={x} y={y} width="110" height="30" rx="6" fill="none" stroke={c} /><text x={x + 55} y={y + 19} textAnchor="middle" fill={c}>{t}</text></g>
  return (
    <Frame label="Vida de una simulación" h={170}>
      {box(10, 70, 'Creada')}{box(150, 70, 'Espera entrada')}{box(290, 70, 'Entrada', accent)}
      {box(440, 10, 'TP1 / TP2', up)}{box(440, 70, 'Stop', down)}{box(440, 130, 'Caducada / invalidada', warn)}
      {[[120, 85, 150, 85], [260, 85, 290, 85], [400, 85, 440, 85], [400, 80, 440, 28], [400, 90, 440, 145]].map(([a, b, c, d], i) => <line key={i} x1={a} y1={b} x2={c} y2={d} stroke={W} markerEnd="url(#ar)" />)}
      <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill={W} /></marker></defs>
    </Frame>
  )
}

export function QuoteVsModelBar() {
  return (
    <Frame label="Bitcoin: cotización en vivo frente a la vela diaria del modelo" h={190}>
      {[[40, 90, 110, 70], [100, 110, 70, 55], [160, 70, 85, 60]].map(([x, o, c, l], i) => <Candle key={i} x={x} o={o} c={c} l={l + 18} h={l - 8} />)}
      <rect x="200" y="50" width="28" height="60" fill="none" stroke={warn} strokeDasharray="3 3" /><text x="190" y="124" fill={warn}>vela abierta: INCOMPLETA</text>
      <line x1="30" x2="330" y1="64" y2="64" stroke={accent} strokeDasharray="2 3" /><text x="240" y="60" fill={accent}>precio en vivo</text>
      <rect x="100" y="150" width="124" height="22" rx="4" fill="none" stroke={up} /><text x="162" y="165" textAnchor="middle" fill={up}>MODEL BAR · cerrada</text>
      <text x="350" y="60">El precio en vivo se actualiza cada 5 s</text>
      <text x="350" y="80">y NUNCA entra en las predicciones.</text>
      <text x="350" y="110">El modelo usa solo velas diarias</text>
      <text x="350" y="126">ya cerradas a las 00:00 UTC.</text>
    </Frame>
  )
}

export function WalkForward() {
  return (
    <Frame label="Validación temporal con holdout sellado" h={150}>
      <rect x="20" y="30" width="200" height="22" fill={accent} opacity="0.35" /><text x="30" y="45">entrenamiento</text>
      <rect x="220" y="30" width="20" height="22" fill={warn} opacity="0.5" /><text x="204" y="70" fill={warn}>purga + embargo</text>
      <rect x="240" y="30" width="80" height="22" fill={up} opacity="0.4" /><text x="250" y="45">validación</text>
      <rect x="20" y="95" width="300" height="22" fill="none" stroke={W} strokeDasharray="3 3" /><text x="26" y="110" fontSize="10">la ventana avanza →</text>
      <rect x="400" y="30" width="140" height="87" fill={down} opacity="0.2" stroke={down} /><text x="470" y="68" textAnchor="middle" fill={down}>HOLDOUT</text><text x="470" y="84" textAnchor="middle" fill={down} fontSize="10">oct-2022 → sep-2025</text>
      <text x="470" y="100" textAnchor="middle" fontSize="10">sellado: nadie lo mira</text>
    </Frame>
  )
}

export function DailyRoutine() {
  const step = (x: number, t: string, s: string) => <g key={t}><rect x={x} y="40" width="100" height="56" rx="6" fill="none" stroke={W} /><text x={x + 50} y="64" textAnchor="middle" fontWeight="600">{t}</text><text x={x + 50} y="82" textAnchor="middle" fontSize="10">{s}</text></g>
  return (
    <Frame label="Rutina diaria de pruebas (forward)" h={140}>
      {step(10, '1 · Datos', 'barras EOD')}{step(125, '2 · Plan', 'reglas por valor')}{step(240, '3 · Decisión', 'entrar / nada')}{step(355, '4 · Paper', 'operación simulada')}{step(470, '5 · Resultado', 'métricas + avisos')}
      <text x="280" y="125" textAnchor="middle" fontSize="10">Un solo paso por día, con el reloj del servidor; repetirlo no duplica nada.</text>
    </Frame>
  )
}
