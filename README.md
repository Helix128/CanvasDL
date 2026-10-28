# CanvasDL

Descargar el material de un semestre completo desde Canvas LMS suele ser bastante tedioso. Ir módulo por módulo abriendo carpetas y bajando PDFs uno por uno toma una eternidad, y lo peor es que muchos profesores enlazan lecturas, pautas o diapositivas dentro de páginas HTML o enunciados de tareas que ni siquiera aparecen en la sección general de archivos.

Hice CanvasDL para solucionar eso. Es una herramienta en Python que se conecta a la API de Canvas y se encarga de recorrer tus ramos, mapear todo el contenido (incluyendo archivos dentro de tareas y páginas) y descargarlo de forma ordenada en tu computador.

Puedes usarlo directamente desde la terminal como comando CLI (que responde en JSON para encadenarlo con otros scripts) o levantarlo como servidor MCP (Model Context Protocol) para integrarlo con asistentes como Claude Code, Claude Desktop o Claude Web. Así puedes pedirle a Claude cosas como *"revisa qué guías entraron en el módulo 3"* o *"descárgame todas las pautas de este ramo"*.

---

## Cómo conectarlo con Claude

CanvasDL implementa el protocolo MCP, así que funciona con cualquier cliente compatible. Dependiendo de cómo trabajes con Claude, tienes tres formas de configurarlo:

### 1. Claude Code (Terminal)

Es la opción más cómoda si ya usas Claude Code en tu máquina, porque corre localmente por `stdio` sin necesidad de exponer puertos.

#### Opción A: Directo con `uvx` (sin clonar el repositorio)
Si tienes instalado `uv`, puedes registrar el servidor con una sola línea:

```sh
claude mcp add canvasdl -e CANVAS_API_TOKEN="tu_token_de_canvas" -- uvx --from git+https://github.com/Helix128/CanvasDL.git canvasdl-mcp
```

*(Si tu universidad tiene un subdominio propio, agrega también `-e CANVAS_BASE_URL="https://tu-universidad.instructure.com"`)*.

#### Opción B: Clonando el repositorio
Si prefieres clonar el repo para modificar el código o correrlo en local:

```sh
git clone https://github.com/Helix128/CanvasDL.git
cd CanvasDL
./install.sh
```

El script `install.sh` crea el entorno virtual (`.venv`), instala dependencias, te pide el token de Canvas (si no lo tienes configurado) y registra el servidor automáticamente en Claude Code, Codex y Antigravity. Al terminar, reinicias tu sesión de Claude Code y queda listo.

---

### 2. Claude Web (claude.ai)

A diferencia de Claude Code, que corre en tu máquina, Claude Web se ejecuta en los servidores de Anthropic. Como no puede ejecutar comandos locales por `stdio`, necesita conectarse a CanvasDL mediante HTTP/SSE (Server-Sent Events) sobre una URL pública con HTTPS.

Tienes dos maneras de resolver esto: dejarlo desplegado en la nube con Render (para no depender de tener tu computador encendido) o correrlo en local y abrir un túnel temporal.

#### Opción A: Desplegar en Render (recomendado para Claude Web)
El repositorio incluye un archivo `render.yaml` listo para desplegar el servidor como Web Service gratuito:

1. Haz un fork del repositorio a tu cuenta de GitHub.
2. Entra a [Render](https://render.com) y crea un nuevo **Web Service** conectado a tu fork (o usa la opción de Blueprints con el `render.yaml`).
3. En las variables de entorno del servicio, configura:
   - `CANVAS_API_TOKEN`: Tu token de Canvas.
   - `CANVAS_BASE_URL`: La URL de tu universidad (por ejemplo `https://tu-universidad.instructure.com`). Si usan el dominio estándar de Canvas, puedes omitirla.
   - `MCP_AUTH_TOKEN`: Una clave secreta inventada por ti (por ejemplo un string largo aleatorio). Servirá para que nadie más pueda usar tu conector.
4. Una vez terminado el despliegue, copia la URL que te da Render (algo como `https://canvasdl-mcp.onrender.com`).
5. En [claude.ai](https://claude.ai), entra a **Configuración** → **Conectores** → **Añadir conector personalizado**:
   - **Nombre:** `CanvasDL`
   - **URL:** `https://canvasdl-mcp.onrender.com/sse` *(es clave poner `/sse` al final)*
   - **Cabeceras:**
     ```
     Authorization: Bearer <tu_MCP_AUTH_TOKEN>
     ```

#### Opción B: Correr en local con un túnel (Cloudflare Tunnel o ngrok)
Si prefieres no subir nada a la nube y usarlo solo cuando estés en tu máquina:

1. Inicia el servidor MCP en modo SSE protegiéndolo con un token de autenticación:
   ```sh
   export MCP_AUTH_TOKEN="una_clave_secreta_segura"
   export CANVAS_API_TOKEN="tu_token_de_canvas"

   canvasdl-mcp --transport sse --host 127.0.0.1 --port 8000 --auth-token "$MCP_AUTH_TOKEN" --allowed-hosts "*"
   ```
   *(Si estás dentro del repo clonado sin instalar el paquete globalmente, ejecuta `.venv/bin/python -m app.mcp_server --transport sse ...`)*.

2. En otra terminal, abre un túnel HTTPS hacia el puerto 8000. Cloudflare Tunnel es muy práctico porque no requiere crear cuenta:
   ```sh
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
   *(Si usas ngrok: `ngrok http 8000`)*.

3. Cloudflare te dará una URL temporal del estilo `https://palabras-aleatorias.trycloudflare.com`. Con esa URL, ve a [claude.ai](https://claude.ai) en **Configuración** → **Conectores** → **Añadir conector personalizado**:
   - **Nombre:** `CanvasDL`
   - **URL:** `https://palabras-aleatorias.trycloudflare.com/sse`
   - **Cabeceras:**
     ```
     Authorization: Bearer una_clave_secreta_segura
     ```

> **Nota sobre descargas en Claude Web:** Como Claude Web vive en la nube y no tiene acceso a tu disco local, no puede guardar archivos directamente en tu carpeta de descargas. Para esos casos, la herramienta `get_file_info(file_id)` te entrega la URL directa del archivo para que la abras en el navegador y lo bajes al instante.

---

### 3. Claude Desktop

Si usas la aplicación de escritorio de Claude (macOS o Windows), solo debes añadir la entrada a tu archivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "canvasdl": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "env": {
        "CANVAS_API_TOKEN": "tu_token_de_canvas",
        "CANVAS_BASE_URL": "https://tu-universidad.instructure.com"
      }
    }
  }
}
```

---

## Seguridad y manejo de archivos

Manejar credenciales universitarias y descargar archivos de forma automatizada tiene sus riesgos si no se toman precauciones. El código incluye varias validaciones específicas para que el proceso sea seguro tanto para tu cuenta como para tu sistema de archivos:

- **Por qué no le mandamos el token a Amazon S3:** Canvas guarda la gran mayoría de los archivos en buckets de Amazon S3 y entrega URLs de descarga pre-firmadas (presigned URLs). Esas URLs ya llevan la autorización codificada en sus parámetros (`X-Amz-Signature`, etc.). Si hicieras la petición enviando la cabecera `Authorization: Bearer <token>`, pasarían dos problemas serios: primero, le estarías regalando tu token privado de Canvas a servidores de Amazon sin ninguna necesidad; y segundo, S3 rechaza la petición de inmediato con un error **HTTP 400** porque detecta dos esquemas de autenticación en conflicto y la descarga falla. CanvasDL analiza el dominio de cada URL antes de hacer el request: solo envía la cabecera con el token si el destino es el dominio oficial de Canvas, y la elimina por completo si va hacia S3 o servicios externos.
- **Protección de rutas en disco (anti Path Traversal):** Los nombres de archivos y carpetas en Canvas los definen los profesores en la plataforma, y a veces contienen caracteres raros, barras, espacios o secuencias como `..`. Si un programa descargara eso concatenando texto sin cuidado, un archivo mal nombrado podría terminar escribiendo fuera de la carpeta de descargas o sobreescribiendo archivos de tu sistema. CanvasDL sanea cada segmento de la ruta quitando caracteres reservados y secuencias relativas. Además, justo antes de escribir el archivo en disco, comprueba con `Path.is_relative_to(directorio_base)` que la ruta absoluta final quede estrictamente dentro de la carpeta designada. Si detecta cualquier intento de salirse, la operación se cancela en el acto.
- **Cómo guardar el token sin subirlo a GitHub:** Tu token de Canvas da acceso total a tus ramos y calificaciones, así que nunca debe terminar en un repositorio público. Tienes dos formas seguras de manejarlo:
  - Mediante variables de entorno (`export CANVAS_API_TOKEN="tu_token"`), que es lo más limpio para terminales y servidores.
  - En un archivo local en `~/.config/canvasdl/canvas_token.txt` con permisos de Unix `0600` (y su carpeta en `0700`), para que únicamente tu usuario del sistema pueda leerlo.
  - Tanto `.gitignore` como la configuración de empaquetado en `pyproject.toml` ignoran explícitamente cualquier archivo `.env`, `.txt` o credencial local para que jamás se incluyan en un commit o en un paquete generado.
- **Operaciones de solo lectura en Canvas:** Todas las consultas a Canvas se hacen mediante métodos `GET`. La herramienta no contiene endpoints ni lógica para enviar tareas, alterar notas o publicar mensajes en foros.
- **Autenticación en tiempo constante para Claude Web:** Cuando levantas el servidor expuesto con HTTP/SSE, el parámetro `--auth-token` exige que cada llamada traiga el Bearer token correcto. La comprobación se hace con `hmac.compare_digest` para evitar ataques de temporización (timing attacks).

---

## Herramientas MCP disponibles

El servidor expone estas herramientas para interactuar con Canvas desde el cliente de IA:

| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `canvas_status()` | Ninguno | Verifica que el token sea válido y devuelve la información del usuario autenticado. |
| `list_courses()` | Ninguno | Lista las asignaturas del usuario, ordenando los cursos activos primero. |
| `list_modules(course_id)` | `course_id` | Muestra los módulos de un curso y los elementos contenidos en cada uno. |
| `list_files(course_id)` | `course_id` | Lista carpetas y archivos del curso, incluyendo aquellos enlazados en páginas o tareas. |
| `list_assignments(course_id)` | `course_id` | Consulta tareas, pautas adjuntas por el profesor y entregas enviadas por el alumno. |
| `course_download_plan(course_id)` | `course_id` | Genera un árbol estructurado con todos los materiales descargables del curso. |
| `get_file_info(file_id)` | `file_id` | Obtiene metadatos y la URL directa de descarga de un archivo (muy útil en Claude Web). |
| `download_course_materials(course_id, destination_dir)` | `course_id`, `destination_dir` (opcional) | Inicia la descarga masiva de todos los materiales del curso en la carpeta indicada o en la caché local. |
| `download_selected_files(course_id, file_ids, destination_dir)` | `course_id`, `file_ids`, `destination_dir` (opcional) | Descarga una selección puntual de archivos identificados en el plan del curso. |
| `canvas_get(path, params, max_items)` | `path`, `params` (opcional), `max_items` (por defecto 500) | Permite consultar cualquier endpoint GET de Canvas (`/api/v1/...`) con paginación automática. |
| `download_files(file_ids, destination_dir)` | `file_ids`, `destination_dir` (opcional) | Descarga una lista de archivos por ID directo a una carpeta. |
| `cached_files()` | Ninguno | Lista los archivos disponibles en la caché local de descargas. |
| `copy_cached_files_to(paths, destination_dir)` | `paths`, `destination_dir` | Copia archivos desde la caché local a otro directorio sin sobreescribir. |
| `download_queue()` | Ninguno | Consulta el estado actual de las descargas en curso y en cola. |
| `cancel_downloads()` | Ninguno | Detiene de inmediato las descargas activas y vacía la cola. |

---

## Uso desde la terminal (CLI)

Si prefieres usar CanvasDL directamente desde la consola sin asistentes de IA, el CLI ofrece comandos prácticos. Todas las respuestas salen en formato JSON estructurado, listo para filtrar con herramientas como `jq` o procesar en scripts propios:

```sh
# Comprobar la conexión y ver tu usuario
python -m app.cli status

# Listar tus cursos
python -m app.cli courses

# Ver módulos, archivos o tareas de un curso
python -m app.cli modules 12345
python -m app.cli files 12345
python -m app.cli assignments 12345

# Generar el plan con todos los materiales del ramo
python -m app.cli plan 12345

# Descargar todo el material de un curso
python -m app.cli download 12345

# Descargar solo archivos específicos por su ID
python -m app.cli download-files 12345 67890 67891

# Ver cómo va la cola de descargas
python -m app.cli downloads
```

*(Si instalaste el paquete con `pip install -e .` o mediante `uv`, también puedes invocar el comando directamente como `canvasdl <comando>` en vez de `python -m app.cli`)*.

---

## Variables de entorno y configuración

CanvasDL busca la configuración en variables de entorno y luego en su archivo local:

- `CANVAS_API_TOKEN` o `CANVAS_TOKEN`: Tu token de acceso de Canvas. Lo generas en Canvas entrando a **Cuenta** → **Configuraciones** → **Nuevo token de acceso**.
- `CANVAS_BASE_URL`: URL de tu institución educativa (por defecto `https://canvas.instructure.com`). Si tu universidad usa un portal propio (por ejemplo `https://miuniversidad.instructure.com`), defínela aquí.
- `MCP_AUTH_TOKEN`: Clave secreta que tú eliges para proteger el servidor cuando lo corres con transporte HTTP/SSE (en Render o mediante un túnel).
- Archivo local de respaldo: Si prefieres no usar variables de entorno en tu máquina, puedes guardar el token en `~/.config/canvasdl/canvas_token.txt` (con permisos `0600` restringidos a tu usuario).
