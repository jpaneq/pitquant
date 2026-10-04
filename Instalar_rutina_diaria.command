#!/bin/bash
# Doble clic para PROGRAMAR la rutina diaria (lunes a viernes 09:30 y 16:00, hora de Madrid) con launchd.
# Para quitarla:  ./Instalar_rutina_diaria.command desinstalar
cd "$(dirname "$0")" || exit 1
LABEL="com.pitquant.daily-routine"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ "$1" = "desinstalar" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$DEST"
  echo "Rutina diaria desinstalada."
  read -r -p "Pulsa Enter para cerrar"
  exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" data
sed "s|/Users/jairo/Proyectos/pitquant|$PWD|g" deploy/launchd/$LABEL.plist > "$DEST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$DEST" && echo "Rutina diaria instalada: $DEST" || echo "No se pudo instalar"
echo "Registro en data/daily-routine.log. Cada ejecución analiza solo las bolsas abiertas en ese momento."
read -r -p "Pulsa Enter para cerrar"
