# Integración del Visor Radiales en la Web IEO

## Contexto

El visor es una aplicación **Streamlit** (Python) que procesa datos CTD del Proyecto RADIALES,
aplica un pipeline de QC + modelo ATAC y los muestra en un interfaz interactivo oscuro.
Audiencia: investigadores internos IEO/CSIC + científicos externos.

---

## Opciones de integración

### Opción A — `<iframe>` embebido *(solución provisional rápida)*

El visor Streamlit corre en un servidor propio o en Streamlit Community Cloud.
La web del IEO lo incrusta con una sola línea HTML:

```html
<iframe src="https://visor-radiales.ieo.es" width="100%" height="900"
        frameborder="0" allowfullscreen></iframe>
```

| | |
|---|---|
| **A favor** | Cero cambios en la web institucional; actualizaciones del visor instantáneas; compatible con cualquier CMS. |
| **En contra** | Necesita servidor Python activo (no es estático); posibles bloqueos CSP/X-Frame-Options; scroll y tipografía aislados del resto de la web; el visor y la web deben compartir protocolo HTTPS. |

**Cuándo elegirla:** cuando haya prisa por mostrar algo y aún no se haya definido la infraestructura.

---

### Opción B — Subdominio propio `visor-radiales.ieo.es` *(recomendada a medio plazo)*

El visor vive en un servidor Linux del IEO (o VPS contratado) con nginx como proxy inverso.
La URL es institucional y el IEO puede optar por enlace directo o iframe.

```
Internet → nginx (TLS, ieo.es) → Streamlit (localhost:8501)
```

| | |
|---|---|
| **A favor** | URL `*.ieo.es`; datos nunca salen de la infraestructura propia; autenticación opcional; control total de versiones. |
| **En contra** | Requiere servidor Linux con Python 3.10+, nginx, certificado TLS; mantenimiento por parte de TI; Streamlit no escala bien con >20 usuarios simultáneos. |

**Cuándo elegirla:** audiencia mixta (investigadores + público), datos no confidenciales, TI dispuesto a mantener una VM.

---

### Opción C — HTML estático generado *(largo plazo)*

Reescritura del visor en Quarto + Observable o en marimo, produciendo un `.html` auto-contenido
que se publica igual que cualquier página web (sin servidor Python).

| | |
|---|---|
| **A favor** | Sin servidor Python; coste de infraestructura nulo; integración nativa con la identidad visual del IEO. |
| **En contra** | Reescritura completa del visor; el pipeline (Polars, ATAC, IF) debe pre-calcularse offline y exportarse como JSON/Parquet; menor interactividad. |

**Cuándo elegirla:** cuando el visor esté maduro y el IEO quiera una solución de mantenimiento mínimo.

---

## Recomendación

| Plazo | Opción |
|---|---|
| Inmediato (demo) | A — iframe sobre Streamlit Community Cloud |
| Medio plazo (producción) | B — subdominio `visor-radiales.ieo.es` en VM Linux |
| Largo plazo (escalable) | C — HTML estático generado con Quarto/marimo |

---

## Preguntas para el webmaster / departamento TI del IEO

Estas respuestas determinan qué opción es viable y cuánto tiempo lleva la integración.

### 1. CMS y estructura web

- ¿Qué CMS gestiona la web del IEO donde se quiere integrar el visor? (Drupal, WordPress, HTML estático, otro)
- ¿Existe una sección ya creada para "herramientas de datos" o "visualizadores" donde encaje el visor, o hay que crear una nueva página?
- ¿La web del IEO es accesible públicamente o requiere login para algunas secciones?

### 2. Infraestructura y hosting

- ¿Dispone el IEO de servidores Linux propios donde pueda alojar un servicio Python persistente (Streamlit)?
- ¿Existe un proceso para aprovisionar una VM o contenedor Docker para nuevas aplicaciones internas?
- ¿Quién gestiona los certificados TLS para subdominios `*.ieo.es`?
- ¿Hay un proxy corporativo (nginx, Apache) ya configurado que pueda añadir un nuevo virtual host?

### 3. Políticas de seguridad

- ¿El servidor web del IEO tiene cabeceras `X-Frame-Options` o `Content-Security-Policy` que bloqueen iframes de orígenes externos?
- ¿Hay restricciones de firewall para abrir puertos de salida (8501) hacia servidores externos?
- ¿Se requiere aprobación del departamento de seguridad para desplegar nuevas aplicaciones web?

### 4. Dominio y DNS

- ¿Tiene el IEO control sobre el DNS de `ieo.es` para añadir subdominios como `visor-radiales.ieo.es`?
- ¿Cuánto tiempo tarda habitualmente un cambio de DNS en ser aprobado y propagado?

### 5. Mantenimiento y SLA

- ¿Quién se responsabiliza de mantener el servidor actualizado (parches de seguridad, Python, dependencias)?
- ¿Hay un proceso de backup o recuperación ante fallos para aplicaciones web internas?
- ¿Cuál es el tiempo de respuesta esperado del TI ante una caída del visor?

### 6. Datos y privacidad

- ¿Los datos CTD del Proyecto RADIALES pueden ser de acceso público (sin autenticación)?
- ¿Hay datos de próximas campañas que deban mantenerse embargados durante un período?
- ¿Se deben anonimizar o eliminar metadatos de proveniencia antes de mostrarlos?

### 7. Estilo y branding

- ¿El IEO tiene una guía de estilo o design system que el visor deba respetar (colores, tipografías, logo)?
- ¿Debe aparecer el logo del IEO-CSIC dentro del propio visor, además de en la página que lo contiene?
- ¿Existe un pie de página institucional obligatorio con información legal / aviso de cookies?

---

## Próximos pasos sugeridos

1. Enviar este documento al webmaster y al responsable TI del IEO para recabar respuestas.
2. Con las respuestas, seleccionar la opción de integración y dimensionar el esfuerzo.
3. Para la demo con Eugenio del CSIC Canarias: usar Streamlit Community Cloud como URL temporal
   (`https://share.streamlit.io/...`) — gratuito, no requiere TI, disponible en horas.
