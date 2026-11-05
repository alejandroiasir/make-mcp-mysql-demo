# Solicitudes ciudadanas → Make

Demo educativa para una clase de automatizaciones con [Make](https://www.make.com). Una app en Python (Streamlit) permite consultar una base MySQL en lenguaje natural mediante un modelo de IA conectado por **MCP**, y enviar la solicitud elegida a un escenario de Make que notifica por correo y la registra en Google Sheets.

El modelo se elige en el `.env`: **Ollama** (local y gratis, por defecto), **OpenAI**, **Claude** (Anthropic) o cualquier servicio compatible con la API de OpenAI, como OpenRouter o Gemini. Ver [Usar otro modelo](#usar-otro-modelo).

> Proyecto de ejemplo con **datos 100% ficticios**. No es un sistema oficial de ninguna institución.

## Cómo funciona

```mermaid
flowchart LR
    U["Usuario"] --> App["App Streamlit<br/>app.py"]
    App <-->|"pregunta / resumen"| IA["Modelo de IA<br/>Ollama, OpenAI o Claude"]
    App <-->|MCP| MCP["Servidor MCP<br/>MySQL (solo lectura)"]
    MCP <--> DB[("MySQL<br/>cne_demo")]
    App -->|"POST JSON"| Make["Webhook de Make"]
    Make --> G["Gmail"]
    Make --> S["Google Sheets"]
    Make -->|"prioridad alta"| A["Alerta"]
```

1. El usuario escribe una pregunta en español.
2. El modelo recibe la estructura de la base y decide qué `SELECT` ejecutar.
3. La app ejecuta la consulta en MySQL a través del servidor MCP y muestra la tabla.
4. El usuario elige una solicitud y la app la envía como JSON al webhook de Make.
5. Make ejecuta el escenario: correo, bitácora y alerta si es urgente.

Make **no se conecta a MySQL**: solo recibe los datos que la app le envía.

## Ahorro de tokens

El modelo nunca lee la base completa: solo ve el texto que la app le envía. La app reduce ese texto así:

| Técnica | Dónde en `app.py` |
|---|---|
| **Contexto una sola vez.** El diccionario de datos (tablas, columnas, tipos y comentarios) se lee de `information_schema` y queda en caché mientras corre la app. El modelo no gasta vueltas explorando la base. | `diccionario_de_datos()` |
| **Prefijo fijo y cacheable.** Instrucciones y estructura van primero y no cambian entre preguntas; es la parte que los proveedores en la nube cachean (*prompt caching*). Con Claude se marca explícitamente con `cache_control`; OpenAI lo hace solo. | `preguntar()`, `proveedores.py` |
| **Solo un resumen vuelve al modelo.** La tabla completa se muestra en pantalla; al modelo le llegan el número de filas y una muestra de 5. | `resumen_para_modelo()` |
| **La base hace el trabajo.** Se le pide al modelo columnas concretas, `COUNT/GROUP BY` para totales y `LIMIT`. | `INSTRUCCIONES` |
| **Consultas frecuentes sin IA.** Las preguntas habituales van directo a MySQL: 0 tokens. | `CONSULTAS_FRECUENTES` |

La app muestra los tokens de entrada y salida de cada consulta con IA, y cuántos se leyeron desde caché, para comparar.

## Requisitos

- Python 3.10 o superior
- Node.js 18 o superior (para ejecutar el servidor MCP con `npx`)
- MySQL 8
- Un modelo de IA que soporte herramientas (*tool calling*), una de estas opciones:
  - [Ollama](https://ollama.com) en tu computador (por defecto `qwen3:8b`, unos 5 GB)
  - Una API key de OpenAI, de Anthropic o de un servicio compatible
- Una cuenta de Make (el plan gratuito alcanza)

## Instalación

```bash
git clone <url-de-este-repo>
cd <carpeta-del-repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Base de datos.** Edita la clave de `cne_lector` en `schema.sql` y carga el archivo:

```bash
mysql -u root < schema.sql
```

Crea la base `cne_demo`, la tabla `solicitudes` con 15 filas ficticias y un usuario de **solo lectura** para el MCP.

**Modelo local** (si usas Ollama, la opción por defecto):

```bash
ollama pull qwen3:8b
```

**Variables de entorno.** Copia el ejemplo y completa tus valores:

```bash
cp .env.example .env
```

| Variable | Valor |
|---|---|
| `LLM_PROVIDER` | `ollama` (por defecto), `openai` o `anthropic` |
| `LLM_MODEL` | Modelo a usar. Vacío: el modelo por defecto del proveedor |
| `LLM_API_KEY` | API key de OpenAI o Anthropic (no se usa con Ollama) |
| `LLM_BASE_URL` | Solo para servicios compatibles con OpenAI (OpenRouter, Gemini...) |
| `MAKE_WEBHOOK_URL` | URL del Custom webhook de tu escenario en Make |
| `MYSQL_HOST`, `MYSQL_PORT` | `127.0.0.1` y `3306` para MySQL local |
| `MYSQL_USER`, `MYSQL_PASS` | `cne_lector` y la clave que pusiste en `schema.sql` |
| `MYSQL_DB` | `cne_demo` |

**Escenario de Make.** Sigue [make_escenario.md](make_escenario.md) para crear el webhook, Gmail, Google Sheets y el Router.

## Uso

```bash
streamlit run app.py
```

- **Consultar con IA:** escribe una pregunta, por ejemplo *"Muéstrame las solicitudes de prioridad alta que siguen pendientes"*.
- **Consultas frecuentes:** en la barra lateral, sin IA.
- **Enviar a Make:** elige una solicitud, escribe un correo de destino en la barra lateral y pulsa el botón.
- **Plan B:** datos de ejemplo para mostrar el flujo sin MySQL ni modelo.

## Usar otro modelo

Cambia solo el `.env` y reinicia Streamlit. El resto de la app (MCP, ahorro de tokens, Make) funciona igual con todos.

| Opción | `LLM_PROVIDER` | `LLM_MODEL` (ejemplo) | `LLM_API_KEY` | `LLM_BASE_URL` |
|---|---|---|---|---|
| **Ollama local** (por defecto) | `ollama` | `qwen3:8b` | — | — |
| **Ollama en la nube** | `ollama` | un modelo con sufijo `-cloud` | — (antes: `ollama signin`) | — |
| **OpenAI** | `openai` | `gpt-5-mini` (por defecto) | tu clave de OpenAI | — |
| **Claude** (Anthropic) | `anthropic` | `claude-opus-5-5` (por defecto) | tu clave de Anthropic | — |
| **OpenRouter** | `openai` | `proveedor/modelo` | tu clave de OpenRouter | `https://openrouter.ai/api/v1` |
| **Gemini** | `openai` | un modelo Gemini | tu clave de Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai/` |

Por ejemplo, para usar Claude:

```
LLM_PROVIDER=anthropic
LLM_API_KEY=tu-clave-de-anthropic
```

Claves: [OpenAI](https://platform.openai.com/api-keys) · [Anthropic](https://console.anthropic.com/settings/keys) · [OpenRouter](https://openrouter.ai/keys) · [Google AI Studio](https://aistudio.google.com/apikey). Revisa en cada servicio qué modelos están disponibles y sus precios: los nombres cambian con el tiempo.

**Notas:**

- El modelo debe soportar herramientas (*tool calling*). Los modelos pequeños pueden equivocarse más con el SQL.
- **Claude:** las instrucciones, la estructura de la base y la herramienta se marcan para *prompt caching*. A partir de la segunda pregunta, esa parte se cobra con descuento si supera el mínimo cacheable del modelo (512 tokens en los modelos actuales). Con `claude-opus-5-5`, `claude-sonnet-5-5` u otros modelos compatibles, si el modelo rechaza una consulta, la API la reintenta sola con otro modelo (*server-side fallback*). Para un modelo más barato, prueba `LLM_MODEL=claude-haiku-5-5`.
- **OpenAI:** cachea automáticamente el inicio repetido del mensaje cuando supera unos 1024 tokens.
- La demo tiene una base pequeña, así que su prefijo puede quedar bajo esos mínimos y no cachearse. Con bases reales, con muchas más tablas, la diferencia se nota.
- Las API keys van solo en `.env`, que no se sube a GitHub.

Toda la conexión con los modelos está en `proveedores.py`: una clase por proveedor con la misma interfaz (`turno()` y `agregar_resultados()`).

## Seguridad

- El servidor MCP usa un usuario MySQL con permiso **solo `SELECT`**: la IA no puede modificar ni borrar datos.
- Con Ollama local todo corre en tu computador: MySQL, MCP y el modelo. Solo sale a internet el JSON que se envía a Make. Con un modelo en la nube, la pregunta, la estructura de la base y el resumen de resultados (hasta 5 filas) viajan además a ese proveedor.
- Una persona elige qué solicitud enviar; la IA no dispara acciones por su cuenta.
- La URL del webhook funciona como una contraseña: va en `.env`, que está en `.gitignore`.
- El servidor MCP ([`@benborla29/mcp-server-mysql`](https://www.npmjs.com/package/@benborla29/mcp-server-mysql)) es de terceros. Para un uso real, revisa su código y fija una versión.
- Con datos reales de personas, revisa la normativa y la política de tu institución antes de usar servicios externos.

## Archivos

| Archivo | Contenido |
|---|---|
| `app.py` | App Streamlit: IA + MCP + envío a Make |
| `proveedores.py` | Conexión con el modelo: Ollama, OpenAI (y compatibles) o Claude |
| `schema.sql` | Base, tabla con comentarios, datos ficticios y usuario de solo lectura |
| `make_escenario.md` | Guía para armar el escenario en Make |
| `guion_clase.md` | Guion de la clase de 60 minutos |
| `.env.example` | Plantilla de variables de entorno |
