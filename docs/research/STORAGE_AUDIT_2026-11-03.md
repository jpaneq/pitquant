# Almacenamiento PITQuant — 3 de noviembre de 2026

Inspección de tamaños y rutas, sin borrar ni modificar bases de datos. Volumen local: 17 GiB disponibles, 92% ocupado. Las cifras no garantizan idéntica recuperación al borrar por posibles bloques compartidos APFS.

## Distribución observada

- data: 89 GiB; archive: 42 GiB; research: 31 GiB (subdirectorios incluidos en los 89, no sumar otra vez).
- Git: 127 MiB; venv principal: 942 MiB; frontend/node_modules: 178 MiB.
- 15 backups antiguos de migración/ingesta: 12,41 GiB de tamaño lógico total.
- Los worktrees de Codex suman aproximadamente 1,5 GiB. El worktree de research tiene data como symlink al directorio principal: no son otros 89 GiB independientes.

## Regenerables, candidatos de bajo impacto

No se han borrado. Las cachés se regeneran; eliminar dependencias obliga a reinstalarlas. Cerrar cualquier proceso de instalación/build antes de limpiar.

- /Users/jairo/Library/Caches/pip — 466 MiB.
- /Users/jairo/.npm/_logs — 92 KiB, logs regenerables. El directorio .npm completo mide 44 MiB, pero no se recomienda borrarlo entero sin revisar su contenido.
- /Users/jairo/Proyectos/pitquant/.mypy_cache — 43 MiB.
- /Users/jairo/Proyectos/pitquant/.pytest_cache — 144 KiB.
- /Users/jairo/Proyectos/pitquant/.ruff_cache — 92 KiB.
- /Users/jairo/.codex/worktrees/us-research-universe-scale-v1/pitquant/.mypy_cache — 39 MiB.
- /Users/jairo/Proyectos/pitquant/frontend/dist — 784 KiB, build regenerable.
- /Users/jairo/Proyectos/pitquant/frontend/node_modules — 178 MiB, reinstalable desde lockfile; no liberarlo si se necesita seguir con frontend sin reinstalar.

## Backups candidatos a traslado y posterior retirada local

No se han comprobado byte a byte contra otras copias ni se han validado como prescindibles para toda investigación. La búsqueda acotada en src/scripts/docs (.py/.md) no encontró referencias a cuatro de los nombres mayores; eso no sustituye la revisión de todos los manifiestos y procesos.

Copiar a disco externo/almacenamiento privado con capacidad, conservar nombre y SHA-256, comprobar integridad de copia y restauración, revisar referencias. Solo entonces retirar el original local. Si se comprimen, verificar que la descompresión reproduce el hash original antes de borrar el .db original. No basta con mover a otra carpeta del mismo volumen.

| Archivo | GiB lógicos |
|---|---:|
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-d02-d05.bak.db | 2.314 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-fin.bak.db | 2.143 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-msci.bak.db | 0.335 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-run3.bak.db | 0.804 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-sec.bak.db | 0.469 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre-yahoo.bak.db | 0.293 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0018.bak.db | 0.237 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0019.bak.db | 0.237 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0020.bak.db | 0.237 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0022.bak.db | 0.293 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0023.bak.db | 0.293 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0024.bak.db | 0.293 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0025.bak.db | 0.804 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0026.bak.db | 1.673 |
| /Users/jairo/Proyectos/pitquant/data/pitquant.pre0027.bak.db | 1.981 |

## Históricos grandes: trasladar, no borrar sin sustituto verificado

- /Users/jairo/Proyectos/pitquant/data/archive — unos 42 GiB; originales de evidencia y procedencia.
- /Users/jairo/Proyectos/pitquant/data/research/us-large-cap-frozen-v1/candidate.db — 9,546 GiB.
- /Users/jairo/Proyectos/pitquant/data/research/us-targeted-closure-v1/candidate.db — 9,546 GiB.
- /Users/jairo/Proyectos/pitquant/data/research/us-universe-scale-v1/candidate.db — 9,499 GiB.

Los tres candidate.db no se han demostrado duplicados; son versiones de investigación. No borrar la base activa data/pitquant.db, .git, modelos/manifiestos, snapshots forward, evidencia original ni worktrees con cambios propios. Evitar VACUUM/copias completas de grandes SQLite con poco espacio; no borrar WAL/SHM para liberar espacio.

## Arquitectura recomendada

Código, configuración sin secretos y documentación en GitHub (ya existe origin https://github.com/jpaneq/pitquant.git). Datos voluminosos y originales en almacenamiento privado/external; conservar local solo el dataset compacto y la base pequeña de seguimiento del piloto. Introducir rutas configurables o enlaces controlados y comprobar que la app resuelve sus rutas después del traslado. La base activa debe migrarse con el proceso detenido o mediante backup SQLite consistente, no una copia arbitraria mientras escribe.

GitHub no sustituye el disco de una ejecución local. Bloquea archivos >100 MiB en Git normal y su documentación desaconseja Git para grandes SQL/backups: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

Ejecutar en Codespaces permite usar una máquina remota, pero requiere trasladar/provisionar datos y tiene cuotas/costes de cómputo y almacenamiento: https://docs.github.com/en/billing/concepts/product-billing/github-codespaces

No se han subido datos, instalado servicios de pago ni eliminado archivos.
