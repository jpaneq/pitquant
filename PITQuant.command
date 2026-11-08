#!/bin/bash
# Doble clic en Finder para lanzar PITQuant (API + Analyzer).
# Primera vez: crea .venv (Python 3.12 vía uv), compila la interfaz y crea la base vacía.
cd "$(dirname "$0")" || exit 1
fail() { echo "ERROR: $1"; read -r -p "Pulsa Enter para cerrar"; exit 1; }

export PITQUANT_DATABASE_URL="${PITQUANT_DATABASE_URL:-sqlite+pysqlite:///data/pitquant.db}"

# 1) Entorno Python (el proyecto exige >=3.12; macOS trae 3.9)
if [ ! -x .venv/bin/python ]; then
  echo "Creando el entorno Python (solo la primera vez)..."
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]" \
      || fail "no se pudo crear el entorno con uv"
  else
    PY=$(command -v python3.13 || command -v python3.12) \
      || fail "necesitas Python 3.12+ (instala uv: curl -LsSf https://astral.sh/uv/install.sh | sh)"
    "$PY" -m venv .venv && .venv/bin/pip install -e ".[dev]" || fail "no se pudo instalar"
  fi
fi
export PATH="$PWD/.venv/bin:$PATH"

# 2) Interfaz
if [ ! -f frontend/dist/index.html ]; then
  echo "Compilando la interfaz (solo la primera vez)..."
  (cd frontend && npm ci && npm run build) || fail "falló la compilación de la interfaz"
fi

# 3) Base de datos (data/ no se versiona): crea/actualiza el esquema
mkdir -p data
alembic upgrade head >/dev/null || fail "falló la migración de la base de datos"

# 4) Puerto: si ya corre PITQuant, ábrelo; si el puerto lo usa otra app, busca otro
PORT="${PITQUANT_PORT:-8000}"
while lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  if curl -s "http://127.0.0.1:$PORT/openapi.json" | grep -q '"title":"PITQuant"'; then
    echo "PITQuant ya está en marcha en el puerto $PORT: abriendo el navegador."
    open "http://127.0.0.1:$PORT/pilotos"
    exit 0
  fi
  PORT=$((PORT + 1))
done

(sleep 3; open "http://127.0.0.1:$PORT/pilotos") &
echo "PITQuant en http://127.0.0.1:$PORT  (Ctrl+C o cierra esta ventana para parar)"
echo "Base vacía? Carga cotizaciones gratuitas con:"
echo "  .venv/bin/python scripts/forward_daily.py --backfill-btc"
exec python -m uvicorn pitquant.api.main:app --port "$PORT"
