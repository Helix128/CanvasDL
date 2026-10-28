---
name: CanvasDL
description: Interfaz Canvas LMS con tema oscuro suave y descargas masivas
colors:
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  canvas-rail: "#141824"
  canvas-sidebar: "#1e2533"
  canvas-base: "#1a202c"
  canvas-card: "#202837"
  canvas-header: "#283344"
  canvas-hover: "#2a3547"
  border-subtle: "#323e52"
  border-strong: "#475569"
  border-input: "#475569"
  text-white: "#ffffff"
  text-primary: "#f8fafc"
  text-secondary: "#cbd5e1"
  text-muted: "#94a3b8"
  status-active: "#10b981"
  file-pdf: "#f87171"
  badge-pdf: "rgba(239, 68, 68, 0.15)"
  file-slide: "#fb923c"
  badge-slide: "rgba(249, 115, 22, 0.15)"
  file-sheet: "#34d399"
  file-zip: "#c084fc"
  badge-zip: "rgba(168, 85, 247, 0.15)"
  file-media: "#38bdf8"
  badge-media: "rgba(14, 165, 233, 0.15)"
  canvas-selected: "#23334d"
  slate-500: "#64748b"
typography:
  display:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  body-sm:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "JetBrains Mono, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  caption:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  micro:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.02em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "10px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text-white}"
    rounded: "{rounded.lg}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
---

# Design System: CanvasDL

## Overview

**Creative North Star: "The Canvas LMS Dark Experience"**

CanvasDL adopta fielmente la estructura visual, jerarquía y familiaridad de Canvas LMS (Instructure), adaptada a un tema oscuro suave (Soft Charcoal Dark Mode) de máxima legibilidad y confort visual. En lugar de negros absolutos, emplea tonos carbón y pizarra (#1a202c, #1e2533, #283344), inspirados en el tema oscuro oficial de Canvas y suites de trabajo modernas.

La arquitectura visual recrea la experiencia canónica de Canvas:
1. **Riel Global de Navegación Canvas**: Barra lateral delgada con logo institucional, acceso de usuario, cursos y descargas.
2. **Panel Secundario de Cursos**: Explorador con buscador y separación destacada de asignaturas activas y favoritas.
3. **Área Principal de Asignatura**: Cabecera con migas de pan (Breadcrumbs), pestañas canónicas de navegación (Módulos / Archivos) y contenedores de módulo idénticos a los de Canvas con chevrons, cabeceras sólidas y filas de archivo con tipografía ampliada (15px/16px) en Source Sans 3.

**Key Characteristics:**
- **Identidad Canvas Auténtica**: Estructura de navegación y acordeones de módulo familiares para cualquier estudiante o docente.
- **Tema Oscuro Suave (Charcoal Dark)**: Sin fatiga visual; fondos en pizarra suave con bordes delimitados de 1px.
- **Tipografía Ampliada de Alta Legibilidad**: Source Sans 3 con escalas de 15px–26px para lectura cómoda y sin esfuerzo.

## Colors

Paleta dark theme suave con contraste optimizado para largas sesiones de estudio.

### Primary
- **Azul Canvas** (#2563eb): Color institucional utilizado en selección activa, estados primarios y botones de acción.

### Neutral
- **Fondo Riel Global** (#141824): Superficie oscura para la barra de navegación global izquierda.
- **Fondo de Barra de Cursos** (#1e2533): Pizarra oscura para la lista de asignaturas.
- **Fondo Base de Trabajo** (#1a202c): Fondo suave para el explorador de contenidos.
- **Cabeceras de Módulo** (#283344): Franjas sólidas que identifican visualmente cada módulo al estilo Canvas.
- **Filas de Archivos** (#202837): Fondo de tarjetas y filas individuales.
- **Bordes Estructurales** (#323e52): Separadores de sección limpios y visibles.
- **Texto Blanco** (#ffffff): Encabezados y títulos principales.
- **Texto Principal** (#f8fafc): Nombres de asignaturas y archivos en 15px.
- **Texto Secundario** (#cbd5e1): Metadatos, docentes y tamaños de archivo.

### Named Rules
**The Soft Dark Rule.** La interfaz nunca utiliza negros puros #000000; todos los fondos se basan en tonos carbón y pizarra (#1a202c a #283344) para preservar el confort visual.

## Typography

**Tipografía Principal:** Source Sans 3  
**Métricas y Códigos:** JetBrains Mono

### Hierarchy
- **Display** (Bold 700, 1.625rem / 26px, line-height 1.25): Título de la asignatura seleccionada.
- **Headline** (SemiBold 600, 1.25rem / 20px, line-height 1.3): Títulos de modales.
- **Title** (SemiBold 600, 1.0625rem / 17px, line-height 1.35): Títulos de módulos Canvas.
- **Body** (Regular 400, 0.9375rem / 15px, line-height 1.5): Nombres de cursos y nombres de archivos.
- **Body Small** (Regular 400, 0.875rem / 14px, line-height 1.45): Metadatos docentes y descripciones.
- **Label** (Medium 500, 0.75rem / 12px, JetBrains Mono): Tamaños en MB/KB y badges de período.

## Layout

Estructura de tres columnas con viewport estricto al 100%:
- Riel global Canvas fijo (64px).
- Panel de asignaturas con scroll independiente (340px).
- Área de trabajo principal con scroll independiente y muelle inferior anclado.

## Elevation & Depth

Diseño tonal Canvas con franjas diferenciadas de color entre cabeceras de módulo (#283344) y filas de contenido (#202837), delimitadas por bordes finos de 1px (#323e52).

## Shapes

- Esquinas de botones y módulos: 8px (`rounded-lg`).
- Checkboxes: 18px x 18px con esquinas de 4px (`rounded`).

## Components

### Canvas Module Container
- Cabecera sólida de módulo con chevron desplegable a la izquierda, título en 17px negrita, contador de archivos y checkbox de selección masiva.
- Filas de items de archivo con icono de documento Canvas, nombre en 15px, tamaño en MB y acción rápida de descarga.

## Do's and Don'ts

### Do:
- **Do** mantener el riel global Canvas, el panel de cursos y el visor de módulos en sus respectivas áreas con scroll independiente.
- **Do** utilizar tamaños de fuente cómodos (15px–26px) para evitar forzar la vista.
- **Do** replicar la apariencia limpia de los módulos de Canvas.

### Don't:
- **Don't** emplear fondos negros puros.
- **Don't** reducir el tamaño de los nombres de archivo por debajo de 14px.
- **Don't** fusionar el scroll del panel lateral con el del área principal.
