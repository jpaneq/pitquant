#!/bin/bash
# Doble clic para PROGRAMAR el ciclo diario de aprendizaje (todos los días a las 23:30).
# Descarga precios (Yahoo + Binance), revisa pronósticos vencidos, emite los nuevos y,
# una vez al mes, reentrena. Nunca abre órdenes.
# Para quitarlo:  ./Instalar_aprendizaje_diario.command desinstalar
cd "$(dirname "$0")" || exit 1
LABEL="com.pitquant.forward-learning"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ "$1" = "desinstalar" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$DEST"
  echo "Aprendizaje diario desinstalado."
  read -r -p "Pulsa Enter para cerrar"
  exit 0
fi
[ -x .venv/bin/python ] || { echo "Primero abre PITQuant.command una vez (crea el entorno)."; read -r -p "Enter"; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" data
sed "s|__PROJECT__|$PWD|g" "deploy/launchd/$LABEL.plist" > "$DEST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$DEST" && echo "Aprendizaje diario instalado: $DEST" || echo "No se pudo instalar"
echo "Registro en data/forward-learning.log. Resultados en http://127.0.0.1:8000/pilotos"
read -r -p "Pulsa Enter para cerrar"
