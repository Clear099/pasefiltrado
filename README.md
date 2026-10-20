# PASE FILTRADO · @pasefiltradonews

Cuenta de Instagram automatizada de noticias de fútbol. Cada día genera y publica entre 6 y 7 posts con el diseño de la marca.

> **Filtramos el ruido. Te pasamos el fútbol.**

---

## 1. Marca

**Nombre.** *Pase filtrado* es el pase que rompe la defensa. También es la noticia que se *filtra* antes que nadie. El nombre es corto, se entiende en toda Latinoamérica y en España, y queda bien como usuario.

**Voz.** Directa, rápida y futbolera, sin clickbait. Siempre cita la fuente. Los rumores se presentan como rumores.

**Estilo oficial: `impacto`** (negro, blanco y rojo; todo inclinado 7°, sensación de velocidad)

| Nombre | Hex | Uso |
|---|---|---|
| Negro | `#080809` | Fondo, con un estadio muy tenue detrás |
| Grafito | `#18181A` | Filas y tarjetas |
| Rojo | `#E61622` | Solo acentos: palabra clave del titular, etiquetas, "VS", marcador del ganador, líneas de velocidad |
| Blanco | `#FFFFFF` | Texto, horarios y marcadores de las listas |
| Gris | `#96989E` | Texto secundario y el equipo que pierde |
| Colores de cada club | — | Anillo de su escudo: el segundo color de cada pieza |

**Tipografía:** **Barlow Condensed** Black Italic para titulares y números, en mayúsculas y con la cursiva a 7°; Barlow Semi Condensed para el texto. El kerning se lee de la propia fuente (`kerning.py`), porque Pillow no lo aplica sin libraqm. El estilo se inspira en la gráfica de transmisiones deportivas, pero no usa tipografías, logos ni nombres de terceros.

**Logo** (`badge.py`, se regenera con `python badge.py`): insignia circular de borde pintado a mano. Adentro hay un estadio de noche con focos, la pizarra táctica (cruces, círculos y flechas de pase), la corona, "PASE" en blanco y "FILTRADO" en rojo con letras de marcador y un subrayado de brocha, y el balón sobre el pasto. Está dibujada entera en código (también la geometría real del balón), así que no depende de fotos de terceros ni necesita créditos. Archivos: `assets/brand/insignia.png` (fondo transparente) y `assets/brand/perfil.jpg` (foto de perfil). En los posts va en chico en el encabezado, junto al nombre.

**Elementos fijos**
- Etiquetas en bloques inclinados: rojas con texto blanco; las especiales ("PARTIDO DEL DÍA", "ÚLTIMA HORA") en blanco.
- Líneas de velocidad rojas y blancas en la esquina superior y una barra roja en el borde inferior.
- Formato vertical 4:5 (1080×1350), que es el que ocupa más espacio en el feed.
- Sin fotos de agencias, porque tienen derechos de autor. Las fotos son libres (Wikimedia Commons) y llevan su crédito.
- Escudos de los clubes solo en partidos y resultados. Vienen de ESPN, quedan en caché en `assets/cache/escudos` y van dentro de un anillo con el color del club. Los escudos oscuros llevan contorno claro; si falta un escudo, se muestran las iniciales sobre el color del club.

**Alternativas** (cambiando `"theme"` en `config.json`): `transmision` (negro y dorado, Oswald) y `editorial` (negro y dorado, Playfair Display).

**Perfil de Instagram**
- Nombre: `Pase Filtrado | Noticias de Fútbol` (el nombre también entra en el buscador).
- Categoría: *Sitio web de noticias y medios*.
- Bio (122 de 150 caracteres):
```
⚽ Champions, ligas top de Europa y Libertadores
🔥 Previas, resultados al instante y fichajes
🌎 Para Latinoamérica y España
```

**Recursos listos:** `assets/brand/perfil.jpg` (foto de perfil) y `assets/brand/destacada-*.jpg` (portadas de historias destacadas).

## 2. Plantillas

| Plantilla | Cuándo se usa | Muestra |
|---|---|---|
| **Previa del partido del día** (carrusel) | Portada, cómo llegan, cara a cara, goleadores y "¿Cómo termina?" | `muestras/hoy-psg-barcelona/` |
| **Resultado al instante** | Portada con foto libre del goleador, marcador con escudos y titular automático ("Doblete de Mbappé…"). Si no hay foto, se usa la tarjeta de escudos | `muestras/portada-foto-resultado.jpg`, `muestras/resultado.jpg` |
| **La fecha en 1 minuto** (carrusel) | Portada con el destacado y "También pasó", el resultado destacado y una slide por liga | `muestras/resultados-del-dia.jpg` |
| Noticia / Fichajes | Con semáforo: sello **PASE COMPLETADO** si está confirmado, etiqueta EN NEGOCIACIÓN o RUMOR si no | `muestras/fichaje-pase-completado.jpg`, `muestras/fichaje-rumor.jpg` |
| Última hora | Hecho confirmado y de impacto | `muestras/ultima-hora-ejemplo.jpg` |
| Dato | Noticia que gira en torno a una cifra | `muestras/dato-ejemplo.jpg` |
| Partidos de hoy | Agenda de la mañana cuando no hay un partido del día | `muestras/agenda.jpg` |

## 3. Cobertura y parrilla diaria

**Qué cubrimos:** la Champions League, las 5 grandes ligas de Europa (LaLiga, Premier League, Serie A, Bundesliga y Ligue 1) y la Copa Libertadores siempre. Del resto del fútbol sudamericano entran solo los partidos importantes: clásicos y duelos de grandes de Argentina, Brasil, Uruguay, Chile y Colombia, la Sudamericana con algún grande, las Eliminatorias y la Copa América. Las ligas y los equipos grandes, separados por región, están en `config.json` (`leagues`, `solo_partidos_grandes`, `big_teams`). El partido del día sale primero de Champions, las 5 grandes y la Libertadores; uno sudamericano solo gana si ese día no hay un duelo de dos grandes en esas competiciones.


Los horarios de la tabla son de Chile, donde corre el bot. En los posts, cada partido muestra la hora de **México, Colombia/Perú/Ecuador, Venezuela/Bolivia, Chile/Argentina/Uruguay/Paraguay y España** con sus banderas; los países se agrupan solos según su hora del día. Detrás de cada post va, muy tenue, una foto libre del estadio del partido (o un estadio genérico), con el crédito en el caption.

El **partido del día** marca la pauta. El bot lo detecta solo, por la liga y por si juegan dos grandes (hoy, PSG–Barcelona), y organiza el día alrededor de él.

| Hora | Post |
|---|---|
| 09:00 | Carrusel de previa del partido del día; si no hay uno, la agenda |
| 13:00 · 18:00 | Noticia elegida por la IA, con prioridad para el partido del día. Si las candidatas son flojas, no publica |
| Cada 15 min (09:00–01:00) | **Monitor**: cuando termina un partido grande, publica el resultado al instante (el partido del día siempre, más hasta 3 por día). Una vez por hora revisa si hay algo de última hora |
| 23:30 | Carrusel "La fecha en 1 minuto" |

Tope: `max_posts_per_day` en `config.json` (8 por defecto). La estrategia completa está en [ESTRATEGIA.md](ESTRATEGIA.md).

## 4. Cómo funciona

```
RSS (Google News, Marca, Mundo Deportivo, BBC) ─┐
API de ESPN (partidos, goles, colores) ─────────┼─► run.py ─► writer.py (Claude) ─► render.py ─► cola
                                                │                                          │
                                                └──────────── publish.py ◄─────────────────┘
                                                              Instagram API
```

- `sources.py` reúne las noticias de las últimas 18 h, elimina duplicados entre medios y trae los partidos.
- `writer.py` usa Claude para elegir la mejor noticia y escribir el titular, la bajada, el caption y los hashtags. Solo usa hechos de la fuente. Sin clave de API funciona igual, pero con el titular original.
- `render.py` dibuja la imagen y `publish.py` la sube a Instagram.
- `data/history.json` evita publicar dos veces lo mismo.
- GitHub Actions ejecuta todo en horario, gratis y sin tener tu PC encendido.

Ligas, feeds, hashtags y cantidad de noticias se cambian en `config.json`.

## 4b. Piloto automático

- **Comentarios (cada hora, `comments.py`).** Claude lee los comentarios nuevos de los posts de los últimos 7 días y decide: responder con la voz de la marca, ocultar (insultos, odio, spam, apuestas) o ignorar. Topes: 20 respuestas por hora, 150 por día y 2 por persona. Todo queda en `data/comentarios.json`. Requiere el permiso `instagram_business_manage_comments`.
- **Estadísticas (cada noche, `metrics.py`).** Alcance, vistas, guardados, envíos, seguidores ganados y visitas al perfil de cada post, más los seguidores diarios, en `data/metricas.json`. Requiere `instagram_business_manage_insights`.
- **Revisión semanal (lunes 10:00, `revision.py`).** Claude analiza la semana por tipo de post y por hora, ajusta `config.json` solo dentro de rangos seguros (cantidad de noticias, horas de noticias, umbrales de resultados y tope diario), guarda el reporte en `reportes/` y abre un *issue* en GitHub para avisar. Con `"revision": {"auto_aplicar": false}` solo propone.
- **Presupuesto (`ia.py`).** Cada llamada a Claude anota su costo en `data/gasto.json`. Con `presupuesto_mensual_usd` (30 por defecto), la revisión de última hora se detiene al 70 % del tope, los comentarios al 90 % y las noticias y la revisión semanal al 100 %.
- **Lo que no se automatiza:** seguir cuentas, dar likes o mandar mensajes en frío. La API no lo permite y hacerlo con bots viola las condiciones de Instagram.

## 5. Puesta en marcha

### Paso 1 · Cuenta de Instagram
1. La cuenta es **@pasefiltradonews** (`HANDLE` en `brand.py`). @pasefiltrado ya lo usa un medio deportivo, así que no lo usamos.
2. Sube `assets/brand/perfil.jpg` como foto de perfil y pega la bio de la sección 1.
3. Pásala a **cuenta profesional**: *Configuración → Tipo de cuenta y herramientas → Cambiar a cuenta profesional → Creador* (o Empresa), en la categoría *Medio de comunicación / noticias*.
4. Crea las historias destacadas con las portadas `assets/brand/destacada-*.jpg`.

### Paso 2 · Repositorio en GitHub
1. En github.com/new crea un repositorio **público** llamado `pasefiltrado`, **vacío**: sin README, sin .gitignore y sin licencia. Tiene que ser público porque Instagram descarga las imágenes desde ahí.
2. Sube el código (el repositorio local ya tiene el primer commit):
   ```bash
   git remote add origin https://github.com/TU_USUARIO/pasefiltrado.git
   git push -u origin main
   ```
3. En *Settings → Actions → General → Workflow permissions*, elige **Read and write permissions**. El bot guarda las imágenes y el historial en el repositorio.

### Paso 3 · App de Meta (para publicar por API)
Antes, @pasefiltradonews tiene que ser **profesional** (Creador o Empresa) y **pública**.

1. Entra a developers.facebook.com con tu cuenta de Facebook. Si es la primera vez, acepta registrarte como desarrollador.
2. **Create App** (arriba a la derecha) → en el caso de uso elige **Other** → **Next** → tipo de app **Business** → **Next**. Solo las apps de tipo Business pueden usar Instagram.
3. Nombre: "Pase Filtrado Bot", tu correo de contacto → **Create app**. Meta te pedirá tu contraseña de Facebook para confirmar. No hace falta conectar un portfolio comercial.
4. En el panel de la app busca el producto **Instagram** → **Set up**. Se agrega solo **API setup with Instagram login**.
5. En la sección **"1. Generate access tokens"**, pulsa **Add account**, inicia sesión con @pasefiltradonews y acepta los permisos.
6. Junto a la cuenta aparece el botón **Generate token**. Cópialo: es el `IG_ACCESS_TOKEN` (dura 60 días; el bot lo renueva solo si cargas `GH_PAT`).
7. No hace falta *App Review* ni pasar la app a *Live*: para publicar en tu propia cuenta basta el acceso estándar.

### Paso 4 · Clave de Claude
En console.anthropic.com, *API Keys → Create Key*. Carga algo de saldo en *Billing*: con la configuración actual el gasto ronda unos centavos de dólar al día.

### Paso 5 · Secretos en GitHub
En el repositorio, *Settings → Secrets and variables → Actions → New repository secret*:

| Secreto | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | La clave del paso 4 |
| `IG_USER_ID` (opcional) | El ID de la cuenta. Si no lo cargas, el bot lo obtiene del token |
| `IG_ACCESS_TOKEN` | El token del paso 3 |
| `GH_PAT` (opcional, recomendado) | Un token *fine-grained* de GitHub (*Settings → Developer settings → Personal access tokens*) solo para este repositorio, con permiso **Secrets: Read and write**. Con él, el token de Instagram se renueva solo cada lunes; sin él, hay que renovarlo a mano antes de los 60 días |

### Paso 6 · Primera prueba
1. *Actions → Publicar → Run workflow* con la opción **`verificar`**: comprueba el token y la cuenta sin publicar nada. El registro debe decir "Conectado a @pasefiltradonews".
2. Luego *Run workflow* con `manana`: debería salir la previa del partido del día (o la agenda).
3. Revisa el post en Instagram. Si algo falla, el registro de la ejecución muestra el error de Instagram.
4. Desde ese momento corre solo según la parrilla de la sección 3.

## 6. Comandos locales

```bash
pip install -r requirements.txt
python run.py --slot demo          # genera muestras en output/demo sin publicar
python run.py --slot manana        # previa del partido del día en la cola
python run.py --slot monitor       # resultado al instante y última hora
python run.py --slot noticias      # deja una noticia en la cola
python publish.py                  # publica la cola (requiere variables IG_* y PUBLIC_BASE_URL)
python publish.py --refresh-token  # renueva el token de 60 días
```
