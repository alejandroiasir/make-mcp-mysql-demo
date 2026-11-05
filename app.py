"""Demo de clase: un modelo de IA consulta MySQL vía MCP y la app dispara un escenario de Make.

El modelo se elige en el .env (Ollama, OpenAI o Claude): ver proveedores.py.

Ahorro de tokens:
- El contexto de la base (diccionario de datos) se obtiene una sola vez y se reutiliza en cada pregunta.
- El modelo solo ve un resumen de los resultados; la tabla completa se muestra directo en pantalla.
- Las consultas frecuentes van directo a MySQL, sin IA (0 tokens).
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from proveedores import MODEL, PROVEEDOR, nueva_conversacion

load_dotenv()

MAX_FILAS_MODELO = 5  # filas de muestra que ve el modelo; el resto solo se muestra en pantalla
COLUMNAS = ["id", "ciudadano", "asunto", "categoria", "prioridad", "estado", "fecha_ingreso"]

INSTRUCCIONES = (
    "Eres un asistente que consulta una base MySQL de solicitudes ciudadanas. "
    "No necesitas explorar la base: abajo tienes su estructura completa. "
    "Usa solo consultas SELECT, pide solo las columnas necesarias, usa COUNT/GROUP BY "
    "cuando pregunten por totales y agrega siempre LIMIT 50. "
    "La tabla de resultados ya se muestra al usuario: no la repitas, resume en 1 o 2 frases en español."
)

# El diccionario se arma desde information_schema: describe la base sin leer sus datos
SQL_DICCIONARIO = (
    "SELECT table_name AS tabla, column_name AS columna, column_type AS tipo, "
    "column_comment AS descripcion FROM information_schema.columns "
    "WHERE table_schema = DATABASE() ORDER BY table_name, ordinal_position"
)

# Preguntas habituales resueltas sin IA: van directo a MySQL y no gastan tokens
CONSULTAS_FRECUENTES = {
    "Pendientes de prioridad alta": (
        "SELECT * FROM solicitudes WHERE prioridad = 'alta' AND estado = 'pendiente' "
        "ORDER BY fecha_ingreso"
    ),
    "Las 5 más antiguas sin resolver": (
        "SELECT * FROM solicitudes WHERE estado <> 'resuelta' ORDER BY fecha_ingreso LIMIT 5"
    ),
    "Total por categoría": (
        "SELECT categoria, COUNT(*) AS total FROM solicitudes GROUP BY categoria ORDER BY total DESC"
    ),
    "Total por estado": (
        "SELECT estado, COUNT(*) AS total FROM solicitudes GROUP BY estado ORDER BY total DESC"
    ),
}

# Plan B si falla MySQL o el modelo: filas de ejemplo sin tocar la base ni la IA
EJEMPLO = [
    {"id": 1, "ciudadano": "Ana Rojas", "asunto": "Cobro excesivo en boleta de luz",
     "categoria": "Tarifas", "prioridad": "alta", "estado": "pendiente", "fecha_ingreso": "2026-10-12"},
    {"id": 6, "ciudadano": "Jorge Díaz", "asunto": "Medidor con lectura errónea",
     "categoria": "Electricidad", "prioridad": "alta", "estado": "pendiente", "fecha_ingreso": "2026-10-05"},
]


def servidor_mysql() -> StdioServerParameters:
    """Lanza el servidor MCP de MySQL como proceso hijo (stdio)."""
    env = {**os.environ, **{
        "MYSQL_HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "MYSQL_PORT": os.getenv("MYSQL_PORT", "3306"),
        "MYSQL_USER": os.getenv("MYSQL_USER", ""),
        "MYSQL_PASS": os.getenv("MYSQL_PASS", ""),
        "MYSQL_DB": os.getenv("MYSQL_DB", "cne_demo"),
    }}
    return StdioServerParameters(
        command="npx", args=["-y", "@benborla29/mcp-server-mysql"], env=env
    )


@asynccontextmanager
async def sesion_mysql():
    """Abre una sesión con el servidor MCP y la cierra al terminar."""
    async with stdio_client(servidor_mysql()) as (read, write):
        async with ClientSession(read, write) as sesion:
            await sesion.initialize()
            yield sesion


async def llamar_herramienta(sesion: ClientSession, nombre: str, argumentos: dict) -> str:
    out = await sesion.call_tool(nombre, argumentos)
    return "".join(c.text for c in out.content if c.type == "text")


def leer_filas(texto: str) -> list:
    """El servidor MCP devuelve las filas como JSON seguido de un texto con el tiempo de la consulta."""
    try:
        datos, _ = json.JSONDecoder().raw_decode(texto.lstrip())
    except ValueError:
        return []
    return datos if isinstance(datos, list) and datos and isinstance(datos[0], dict) else []


async def consultar(sql: str) -> list:
    """Ejecuta un SELECT directo por MCP, sin pasar por el modelo."""
    async with sesion_mysql() as sesion:
        return leer_filas(await llamar_herramienta(sesion, "mysql_query", {"sql": sql}))


@st.cache_data(show_spinner=False)
def diccionario_de_datos() -> str:
    """Contexto de la base para el modelo. Se calcula una vez y queda en caché mientras corre la app."""
    lineas = []
    for f in asyncio.run(consultar(SQL_DICCIONARIO)):
        descripcion = f": {f['descripcion']}" if f.get("descripcion") else ""
        lineas.append(f"- {f['tabla']}.{f['columna']} ({f['tipo']}){descripcion}")
    return "\n".join(lineas)


def resumen_para_modelo(texto: str, filas: list) -> str:
    """Lo único que vuelve al modelo: cuántas filas hay y una muestra pequeña."""
    if not filas:
        return texto[:1000]  # sin filas (vacío o error): basta con el mensaje, recortado
    muestra = json.dumps(filas[:MAX_FILAS_MODELO], ensure_ascii=False, default=str)
    return (
        f"{len(filas)} filas, columnas: {', '.join(filas[0])}. "
        f"Muestra de {min(len(filas), MAX_FILAS_MODELO)}: {muestra}"
    )


async def preguntar(pregunta: str, contexto: str):
    """El modelo decide qué consulta hacer; las tools vienen del servidor MCP."""
    filas = []
    async with sesion_mysql() as sesion:
        herramientas = (await sesion.list_tools()).tools
        # Primero lo fijo (instrucciones + estructura), al final la pregunta: ese prefijo
        # repetido es lo que los proveedores en la nube cachean (prompt caching).
        conversacion = nueva_conversacion(
            f"{INSTRUCCIONES}\n\nEstructura de la base:\n{contexto}", pregunta, herramientas
        )
        for _ in range(5):  # tope de vueltas por si un modelo pequeño se queda repitiendo consultas
            texto, llamadas = await conversacion.turno()
            if not llamadas:
                return texto, filas, conversacion.uso
            resultados = []
            for llamada in llamadas:
                salida = await llamar_herramienta(sesion, llamada.nombre, llamada.argumentos)
                filas = leer_filas(salida) or filas  # la tabla completa se queda en la app
                resultados.append((llamada, resumen_para_modelo(salida, filas)))
            conversacion.agregar_resultados(resultados)
    return "El modelo no logró terminar la consulta; intenta reformular la pregunta.", filas, conversacion.uso


def completar_fila(fila: dict) -> dict:
    """Make espera todas las columnas; si la consulta trajo solo algunas, se busca la fila completa."""
    if all(c in fila for c in COLUMNAS):
        return fila
    filas = asyncio.run(consultar(f"SELECT * FROM solicitudes WHERE id = {int(fila['id'])}"))
    return filas[0] if filas else fila


def enviar_a_make(fila: dict, correo: str) -> requests.Response:
    """Un JSON plano por solicitud: es lo más fácil de mapear en Make."""
    payload = {
        "origen": "app-cne-demo",
        "enviado": datetime.now().isoformat(timespec="seconds"),
        "correo_destino": correo,
        **{k: str(v) for k, v in fila.items()},
    }
    return requests.post(os.environ["MAKE_WEBHOOK_URL"], json=payload, timeout=15)


def causa(e: Exception) -> Exception:
    """Desempaca los errores anidados que lanza el TaskGroup de MCP."""
    while getattr(e, "exceptions", None):
        e = e.exceptions[0]
    return e


def mostrar_resultado(filas: list, respuesta: str, uso: dict | None = None):
    st.session_state.update(filas=filas, respuesta=respuesta, uso=uso)


st.set_page_config(page_title="Solicitudes + Make", page_icon="⚡")
st.title("⚡ Solicitudes ciudadanas → Make")
st.caption(f"Modelo: {PROVEEDOR} · {MODEL}. Consulta MySQL por MCP; Make hace el resto. Datos ficticios.")

with st.sidebar:
    correo = st.text_input("Correo de destino de la demo")

    st.subheader("Consultas frecuentes")
    st.caption("Van directo a MySQL, sin IA: 0 tokens.")
    frecuente = st.selectbox("Consulta", list(CONSULTAS_FRECUENTES), label_visibility="collapsed")
    if st.button("Ejecutar sin IA"):
        try:
            mostrar_resultado(asyncio.run(consultar(CONSULTAS_FRECUENTES[frecuente])), f"**{frecuente}**")
        except Exception as e:
            st.error(f"No se pudo consultar: {causa(e)}")

    st.divider()
    if st.button("Usar datos de ejemplo (Plan B)"):
        mostrar_resultado(EJEMPLO, "(Datos de ejemplo, sin IA ni MySQL)")

    if "contexto" in st.session_state:
        with st.expander("Contexto de la base que ve el modelo"):
            st.code(st.session_state["contexto"], language="text")

pregunta = st.text_input(
    "Pregunta", placeholder="Muéstrame las solicitudes de prioridad alta que siguen pendientes"
)
if st.button("Consultar con IA") and pregunta:
    with st.spinner("El modelo consulta MySQL vía MCP (puede tardar unos segundos)..."):
        try:
            contexto = diccionario_de_datos()
            st.session_state["contexto"] = contexto
            respuesta, filas, uso = asyncio.run(
                asyncio.wait_for(preguntar(pregunta, contexto), timeout=120)
            )
            mostrar_resultado(filas, respuesta, uso)
        except Exception as e:
            st.error(f"No se pudo consultar: {causa(e)}")

if "respuesta" in st.session_state:
    st.write(st.session_state["respuesta"])
filas = st.session_state.get("filas", [])
uso = st.session_state.get("uso")
if uso:
    cache = f" ({uso['cache']} desde caché)" if uso.get("cache") else ""
    st.caption(
        f"Tokens: {uso['entrada']} de entrada{cache} · {uso['salida']} de salida · "
        f"el modelo vio {min(len(filas), MAX_FILAS_MODELO)} de {len(filas)} filas"
    )
if filas:
    st.dataframe(pd.DataFrame(filas), width="stretch")

if filas and "id" in filas[0]:  # los totales por categoría/estado no son solicitudes que notificar
    elegida = st.selectbox(
        "Solicitud a notificar",
        filas,
        format_func=lambda f: f"#{f['id']} · {f.get('asunto', '')}",
    )
    if st.button("Enviar a Make"):
        if not correo or not os.getenv("MAKE_WEBHOOK_URL"):
            st.warning("Falta el correo de destino (barra lateral) o MAKE_WEBHOOK_URL en .env")
        else:
            try:
                fila = completar_fila(elegida)
            except Exception:
                fila = elegida  # sin MySQL (Plan B) se envía la fila tal como está
            r = enviar_a_make(fila, correo)
            st.success(f"Make respondió {r.status_code}: {r.text}")
