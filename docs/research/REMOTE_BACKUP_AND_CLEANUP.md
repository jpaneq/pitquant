# Continuar desde Git y retirar datos locales

El código se guarda en la rama `codex/forward-pilots-v1` de jpaneq/pitquant.
El repositorio de código es público. Las bases y originales se almacenan como
assets de Releases en **jpaneq/pitquant-backups, privado**; no como commits Git.
No se publican credenciales. GitHub almacena archivos, pero no ejecuta por sí
solo la app, ingesta o entrenamiento: hace falta un ordenador, servidor o
Codespace con almacenamiento. No se ha contratado ni iniciado cómputo de pago.

## Copias

- Los 15 backups antiguos: release `database-backups-2026-11-03`. Las tres
  partes subidas y la reconstrucción completa de sus 15 originales ya se
  comprobaron por SHA-256. No se han retirado los originales.
- Copia completa: release `full-project-2026-11-03-v2`. Incluye código,
  datos principales, artefactos científicos, los dos worktrees y un bundle de
  todas las referencias Git. El symlink compartido de datos no se duplica.
  Se excluyen entornos/cachés regenerables, credenciales y temporales de subida.
  **La subida no basta: exigir FULL_RESTORE_VERIFIED.json antes del borrado.**
- La release `full-project-2026-11-03` del primer intento es incompleta y
  nunca sirve para restaurar o autorizar borrado.

## Preparación y comprobación (sin borrar)

Desde la raíz, usando Python 3.12 y `gh` autenticado con acceso al repo privado:

```sh
python3 scripts/project_backup.py verify --tag full-project-2026-11-03-v2
python3 scripts/local_data_cleanup.py --tag full-project-2026-11-03-v2
```

La primera descarga las partes como flujo y reconstruye cada archivo solo
para comprobar su hash, sin guardar otra copia de 89 GiB. La segunda revisa
los archivos locales contra esa copia. Se bloquea si faltan pruebas de
restauración, hay archivos nuevos/modificados, WAL/journals o ficheros en uso.
Cerrar la app y parar ingestas/automatizaciones antes de esta comprobación.
No deben ejecutarse escrituras concurrentes durante comprobación/borrado.

## Comando de retirada local (NO ejecutado por el asistente)

Ejecutar únicamente tras restaurar/probar la app en el destino elegido y
obtener la comprobación anterior satisfactoria:

```sh
python3 scripts/local_data_cleanup.py --tag full-project-2026-11-03-v2 \
  --stop-app --execute --confirm DELETE_BACKED_UP_LOCAL_DATA
```

La opción `--stop-app` detiene únicamente el servidor PITQuant del proyecto
en el puerto 8000, verificando su carpeta y proceso; no mata otras aplicaciones.
Parar aparte cualquier ingesta o automatización.

Elimina solo archivos dentro de los directorios data incluidos en la copia y
cuyo hash sigue coincidiendo. Conserva código, .git, credenciales, entornos y
recibos de backup. No sigue symlinks. No promete liberar exactamente el tamaño
lógico por bloques compartidos APFS. Los temporales de subida y entornos no
son datos científicos y quedan aparte, identificados en STORAGE_AUDIT.
No usar `rm -rf pitquant`: no verifica cambios posteriores ni conserva Git.

Si el chequeo detecta datos posteriores, crear otra copia completa con un tag
nuevo y verificarla; no forzar el borrado ni ignorar el bloqueo.

## Recuperar y trabajar en otro equipo/servidor/Codespace

```sh
git clone --branch codex/forward-pilots-v1 https://github.com/jpaneq/pitquant.git
cd pitquant
gh auth status
python3 scripts/project_backup.py restore --tag full-project-2026-11-03-v2 \
  --destination "$HOME/pitquant-restored"
```

La restauración completa reproduce los archivos bajo `project/`, `worktrees/`
y `git/`; preserva hashes. Elegir siempre destino nuevo. El código clonado es
la base de trabajo; restaurar `project/data/` a su carpeta data y configurar
PITQUANT_DATABASE_URL a la base restaurada. Reconstruir entorno con Python3.12:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,postgres,localpg]'
(cd frontend && npm ci && npm run build)
export PYTHONPATH="$PWD/src"
export PITQUANT_DATABASE_URL="sqlite+pysqlite:///$PWD/data/pitquant.db"
.venv/bin/python -m uvicorn pitquant.api.main:app --host 127.0.0.1 --port 8000
```

Para una app ligera, `restore --minimal` conserva únicamente base activa,
artefactos forward, informes y datos BTC del worktree. Aun así verifica todo el
flujo remoto; no se pierden los históricos, siguen en la copia privada. Esa
base activa ocupa ~3,6 GiB y el entorno/dependencias también necesitan espacio.
En Codespaces exponer el puerto 8000 solo de forma privada. No poner secretos
ni datos privados en el repositorio público. Tras un clone limpio, la carpeta `data` no existe: trasladar la restaurada
con `mv "$HOME/pitquant-restored/project/data" ./data` antes de iniciar.
Credenciales deben configurarse
de nuevo en el equipo de destino; no forman parte del backup.

El bundle Git permite recuperar ramas locales que no se hubiesen subido:
`git bundle list-heads <ruta>/git/all-refs.bundle`.
