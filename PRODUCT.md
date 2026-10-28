# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
FastAPI (Python backend con integración directa a Canvas LMS API y autenticación Playwright/SSO) + Frontend web reactivo moderno (HTML5, Tailwind CSS, JavaScript modular nativo, Lucide Icons) servido localmente.

## Users
Estudiantes universitarios que necesitan acceder de forma ágil a sus asignaturas en Canvas LMS, explorar materiales docentes y descargar masivamente archivos, módulos y carpetas para estudio offline o respaldo de cursos activos e históricos.

## Product Purpose
Proporcionar una interfaz visual fluida, cómoda y moderna para Canvas LMS que supere la lentitud y las descargas individuales de la interfaz web estándar. Permite navegar por cursos activos e inactivos (priorizando visualmente los activos), explorar módulos y carpetas en árbol con previsualización de metadatos, y realizar descargas masivas (bulk downloads) con progreso en tiempo real y organización jerárquica limpia en disco local.

## Positioning
Un gestor y descargador local-first ("Canvas Companion / Bulk Downloader") para estudiantes universitarios que automatiza la autenticación universitaria compleja (SSO institucional con cookies y tokens generados automáticamente) y transforma la tediosa tarea de descargar decenas de diapositivas y lecturas curso por curso en una experiencia fluida, rápida y con un par de clics.

## Operating Context
El usuario ejecuta la aplicación localmente en su entorno de desarrollo/escritorio. La aplicación interactúa con la API REST de Canvas (`https://canvas.instructure.com/api/v1/...` o la instancia de su institución) utilizando el token de API guardado o generado vía SSO Playwright. Las descargas se gestionan y guardan en el sistema de archivos local organizadas por curso y módulo (`~/Downloads/CanvasDL/[Curso]/[Módulo]/[Archivo]`).

## Capabilities and Constraints
- **Autenticación Institucional**: Aprovecha la sesión existente de Playwright y el generador/verificador de API tokens ya probado en `main.py`.
- **Listado y Priorización de Cursos**: Consulta `/api/v1/courses`, separando y destacando visualmente los cursos activos (semestre en curso) frente a los concluidos o inactivos.
- **Exploración Jerárquica de Contenidos**:
  - Exploración por Módulos y sus Items (`/api/v1/courses/:id/modules`).
  - Exploración por Archivos y Carpetas (`/api/v1/courses/:id/files`, `/folders`).
  - **Recuperación de Archivos Ocultos y Enlazados**: Motor de escaneo concurrente que extrae archivos referenciados en Páginas, Tareas, Módulos y Anuncios cuando la pestaña de Archivos está restringida por el docente (HTTP 403) o los archivos no están catalogados en carpetas públicas.
  - **Hub de Tareas (Assignments)**: Vista dedicada que clasifica tareas por estado (pendientes, entregadas, calificadas), permitiendo descargar materiales docentes (pautas, lecturas), enunciados en HTML y entregas enviadas por el estudiante.
- **Descarga Masiva (Bulk Download)**:
  - Selector interactivo con checkboxes (selección de todo el curso, módulos completos, carpetas o archivos específicos).
  - Descarga asíncrona concurrente con reporte de progreso en vivo por archivo y global.
  - Creación limpia de rutas y carpetas locales (sanitización de nombres de archivo).
  - Detección de archivos ya existentes para evitar re-descargas innecesarias.
- **Modo Operativo**: Aplicación web local accesible en `http://localhost:8000`, sin telemetría externa ni exposición de credenciales.

## Brand Commitments
- Nombre: CanvasDL
- Voz y estilo: Herramienta de productividad de estudio de alto rendimiento: limpia, rápida, funcional (inspirada en interfaces modernas como Raycast/Linear).

## Evidence on Hand
- Código existente probado en `main.py`:
  - Manejo de cookies SSO con Playwright (`session.json`).
  - Creación y verificación de tokens de API en `canvas_token.txt`.
  - Conexión funcional validada con la API de Canvas LMS.

## Product Principles
1. **Velocidad y Cero Fricción**: La aplicación debe responder de inmediato; listar cursos y abrir módulos debe sentirse instantáneo comparado con el portal web de Canvas.
2. **Prioridad Visual Clara**: Cursos activos primero y destacados; cursos antiguos accesibles pero discretos.
3. **Control y Transparencia en Descargas**: El usuario siempre sabe qué seleccionó, tamaño estimado, progreso en tiempo real y la ubicación exacta de guardado.
4. **Resiliencia Local**: Manejo transparente de reintentos, tokens expirados y fallos de conexión.
