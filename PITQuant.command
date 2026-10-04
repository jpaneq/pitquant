#!/bin/bash
# Doble clic en Finder para lanzar PITQuant (API + Analyzer) en http://127.0.0.1:8000
cd "$(dirname "$0")" || exit 1
export PATH="$PWD/.venv/bin:$PATH"
export PITQUANT_DATABASE_URL="${PITQUANT_DATABASE_URL:-sqlite+pysqlite:///data/pitquant.db}"

if [ ! -f frontend/dist/index.html ]; then
  echo "Compilando la interfaz (solo la primera vez)..."
  (cd frontend && npm ci && npm run build) || { echo "Falló la compilación"; read -r -p "Pulsa Enter para cerrar"; exit 1; }
fi

if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "PITQuant ya está en marcha: abriendo el navegador."
  open "http://127.0.0.1:8000/analyzer/AAPL"
  exit 0
fi

(sleep 3; open "http://127.0.0.1:8000/analyzer/AAPL") &
echo "PITQuant en http://127.0.0.1:8000  (Ctrl+C o cierra esta ventana para parar)"
exec python -m uvicorn pitquant.api.main:app --port 8000
