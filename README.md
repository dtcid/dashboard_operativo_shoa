# Red de boyas SNAM — Dashboard de estado operativo

Autor: CF Felipe Rifo Espósito · feliperifo@gmail.com

## Qué hay en esta carpeta

| Archivo | Función |
|---|---|
| `index.html` | El dashboard. Abre en el **resumen** (1. Estaciones · operatividad, 2. Personal en comisión, 3. Noticias) y el botón **Ver mapa** (o la dirección `…/#mapa`) muestra estaciones, unidades y personal desplegado. Autocontenido, con una instantánea del último estado conocido. |
| `colector.py` | Consulta las fuentes y escribe `estado.json`. Solo biblioteca estándar de Python. |
| `.github/workflows/estado.yml` | Ejecuta el colector cada 10 minutos y publica el sitio en GitHub Pages. |
| `estado.json` | Estado inicial (2 de octubre de 2026). El flujo lo reemplaza en cada ejecución. |

## Fuentes del estado

- **Boyas de oleaje** (Iquique, Antofagasta, Concón, San Antonio, Talcahuano, Desertores, Punta Arenas): series horarias de 7 días del visor web de boyas. Una hora sin `idBoya` cuenta como hora sin dato.
- **Boyas DART** (Iquique, Mejillones, Caldera, Pichidangui, Constitución): archivos de tiempo real de NOAA/NDBC (estaciones 32401, 32403, 32402, 32404 y 34420).
- **Noticias**: las publicaciones de portada del sitio institucional.

## Semáforo

| Estado | Oleaje | DART |
|---|---|---|
| Operativa | último dato ≤ 3 h | último dato ≤ 6 h |
| Con retraso | 3–24 h | 6–24 h |
| No operativa | > 24 h o sin datos en 7 días | > 24 h o sin archivo en NDBC |

Además se marca con ⚠ una DART en modo evento y una boya cuyo GPS la ubica fuera de su círculo de borneo.
El dashboard recalcula el semáforo cada minuto con la hora del equipo, de modo que una boya pasa a "con retraso" aunque el colector se detenga. Si `estado.json` tiene más de 40 minutos, aparece un aviso.

## Puesta en marcha en GitHub (≈10 minutos)

1. Crear un repositorio **público** nuevo (Actions y Pages son gratuitos en repositorios públicos).
2. Subir los cuatro elementos de esta carpeta, incluida la carpeta oculta `.github`.
3. En *Settings → Pages → Build and deployment → Source*, elegir **GitHub Actions**.
4. En la pestaña *Actions*, abrir "Estado de la red de boyas" y pulsar **Run workflow**.
5. El sitio queda en `https://<usuario>.github.io/<repositorio>/`.

Notas operativas:

- El cron de GitHub no es puntual: con carga, una ejecución de cada 10 minutos puede atrasarse o saltarse. Para mayor regularidad, un equipo externo puede llamar al evento `repository_dispatch` con tipo `actualizar`.
- GitHub **desactiva los flujos programados de un repositorio público tras 60 días sin actividad**. Un commit cualquiera, o reactivarlo desde la pestaña Actions, lo vuelve a encender.
- Las fuentes no son API documentadas. Si cambian, el colector registra el error en `estado.json` (campo `errores`) y la boya afectada aparece como no operativa.

## Buques en sondaje

El registro de buques, posiciones y dotaciones **se guarda solo en el navegador de cada equipo** y nunca se envía al sitio publicado: GitHub Pages es público aunque el repositorio sea privado. Para compartir el registro se usa *Exportar registro* (archivo `.json`) y *Cargar registro* en el otro equipo, por un canal autorizado.

La posición se puede escribir en grados y minutos (`36°42.50′S`, `073°07.20′W`), en decimal (`-36.7083`) o marcar con un clic en el mapa.

## Carga de información por área

Cada área del resumen tiene sus propios botones **Cargar**, **Ver texto** y **Quitar**, y muestra cuándo se cargó:

1. **Estaciones · operatividad**: se pega el bloque de material del SITREP (nivel del mar, DART, meteoceánicas, glider) y, si corresponde, los mensajes navales. Al final del área aparece el **contraste informe ↔ monitor**: diferencias entre el resumen inicial y la sección Material, conteos que no cuadran y boyas cuyo estado declarado no coincide con lo que el monitor recibe. Un clic en una observación lleva a la boya en el mapa.
2. **Personal en comisión**: se pega el personal (Oficiales, GM, Empleados Civiles, PAC), las comisiones y las embarcaciones. Las unidades pasan al mapa con su dotación; si el lugar es conocido (Talcahuano, Chungungo, Punta de Choros, Caleta Higuerillas, Punta Arenas, Bahía Cook, Valparaíso) se ubican en una **posición aproximada** marcada como tal, que se corrige con ✎ en el mapa.
3. **Noticias**: se pegan noticias propias, separadas por una línea en blanco (primera línea, título). Aparecen antes de las de la portada que trae el colector.

En cualquiera de las dos primeras áreas también se puede pegar el SITREP completo: cada una toma solo lo que le corresponde.

En pantallas anchas, cada área se desplaza por separado y las otras dos quedan fijas.

Los textos cargados y el registro de unidades **se guardan solo en el navegador de cada equipo y nunca se publican**. El `index.html` de esta carpeta no contiene ningún SITREP.

## Probar sin red

```
SAMPLES_DIR=muestras python3 colector.py
```

lee respuestas guardadas (`wave_<id>.txt`, `dart_<id>.txt`, `news.json`) en lugar de consultar las fuentes.
