# Bases de los parches de engine

`surfer.json` fija el producto base en Firefox `158.0.1` (`candidateBuild: 1`).
El árbol fuente limpio correspondiente está representado en el repositorio de
engine por el commit `3d098c88f09123d85d962d59e6c3e4a6aada214f`, titulado
`Firefox 158.0.1`.

El motor de trabajo tiene como `HEAD` el commit
`4638bf34feb43dd2e374f481dce33920aa5a0591`, hijo directo de esa base. Ese
commit añade accesos directos a la página de inicio y la integración inicial de
IA local. Por tanto, el motor actual no es el árbol Firefox limpio fijado en
`surfer.json`, aunque ambos indiquen la versión `158.0.1`. La importación de
esta tarea mantuvo ese `HEAD` y los cambios sin commit del usuario.

Los parches persistentes de `browser-box.inc.xhtml`, `preferences.js`,
`preferences.xhtml` y `config/account-sync.mjs` se consolidaron contra la base
`3d098c88…`. Incluyen la barra lateral opcional de IA local y conservan la
limpieza aprobada de General. La regeneración se comprobó en un árbol hermano
construido desde esa base, así que esos parches no dependen del commit local
posterior. Surfer aplicó los 285 parches de Git. La importación completa se
repitió y los SHA-256 de los 484 082 archivos de engine coincidieron entre
pasadas (cero diferencias). `npm run import` también
ejecuta el sincronizador Fluent inglés y lleva los catálogos españoles de
Preferencias y bienvenida a las rutas que usa el merge de locales. Estos pasos
actualizan los recursos `zen*` propios y conservan los recursos base de Firefox.
Surfer avisó que existe
Firefox `159.0.1` más reciente; no se actualizó la versión fijada.
