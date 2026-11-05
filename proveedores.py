"""Conexión con el modelo de IA: Ollama (local o nube), OpenAI (y compatibles) o Claude.

Cada proveedor guarda la conversación en su propio formato, pero todos ofrecen lo mismo:
- turno(): envía la conversación y devuelve (texto, llamadas a herramientas)
- agregar_resultados(): devuelve al modelo lo que respondieron las herramientas
- uso: tokens de entrada, salida y leídos desde caché
"""
import json
import os
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from ollama import AsyncClient as AsyncOllama
from openai import AsyncOpenAI

load_dotenv()

PROVEEDOR = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
MODELOS_POR_DEFECTO = {"ollama": "qwen3:8b", "openai": "gpt-5-mini", "anthropic": "claude-opus-5-5"}
MODEL = os.getenv("LLM_MODEL") or MODELOS_POR_DEFECTO.get(PROVEEDOR, "")
API_KEY = os.getenv("LLM_API_KEY") or None  # vacío: cada SDK busca OPENAI_API_KEY o ANTHROPIC_API_KEY
BASE_URL = os.getenv("LLM_BASE_URL") or None  # para OpenRouter, Gemini u otro servicio compatible

# Modelos de Claude que aceptan el respaldo automático si rechazan una consulta
CLAUDE_CON_RESPALDO = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


@dataclass
class Llamada:
    id: str
    nombre: str
    argumentos: dict


def esquema(herramienta) -> dict:
    """El JSON Schema de una herramienta MCP, sin la clave $schema que algunos proveedores rechazan."""
    return {k: v for k, v in herramienta.input_schema.items() if k != "$schema"}


def formato_funcion(herramientas) -> list:
    """Formato de herramientas que usan Ollama y OpenAI."""
    return [
        {"type": "function", "function": {
            "name": t.name, "description": t.description or "", "parameters": esquema(t)}}
        for t in herramientas
    ]


class Ollama:
    def __init__(self, sistema: str, pregunta: str, herramientas):
        self.cliente = AsyncOllama()  # http://localhost:11434, o lo que diga OLLAMA_HOST
        self.tools = formato_funcion(herramientas)
        self.mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": pregunta}]
        self.uso = {"entrada": 0, "salida": 0, "cache": 0}

    async def turno(self):
        r = await self.cliente.chat(model=MODEL, messages=self.mensajes, tools=self.tools, think=False)
        self.uso["entrada"] += r.prompt_eval_count or 0
        self.uso["salida"] += r.eval_count or 0
        self.mensajes.append(r.message)
        llamadas = [
            Llamada(c.function.name, c.function.name, dict(c.function.arguments))
            for c in r.message.tool_calls or []
        ]
        return r.message.content or "", llamadas

    def agregar_resultados(self, resultados):
        for llamada, texto in resultados:
            self.mensajes.append({"role": "tool", "tool_name": llamada.nombre, "content": texto})


class OpenAI:
    def __init__(self, sistema: str, pregunta: str, herramientas):
        self.cliente = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.tools = formato_funcion(herramientas)
        # OpenAI cachea solo el inicio repetido del mensaje (desde ~1024 tokens): lo fijo va primero
        self.mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": pregunta}]
        self.uso = {"entrada": 0, "salida": 0, "cache": 0}

    async def turno(self):
        r = await self.cliente.chat.completions.create(
            model=MODEL, messages=self.mensajes, tools=self.tools
        )
        if r.usage:
            self.uso["entrada"] += r.usage.prompt_tokens
            self.uso["salida"] += r.usage.completion_tokens
            detalle = r.usage.prompt_tokens_details
            self.uso["cache"] += (detalle.cached_tokens or 0) if detalle else 0
        mensaje = r.choices[0].message
        funciones = [c for c in mensaje.tool_calls or [] if c.type == "function"]
        asistente = {"role": "assistant", "content": mensaje.content or ""}
        if funciones:
            asistente["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in funciones
            ]
        self.mensajes.append(asistente)
        llamadas = [
            Llamada(c.id, c.function.name, json.loads(c.function.arguments or "{}"))
            for c in funciones
        ]
        return mensaje.content or "", llamadas

    def agregar_resultados(self, resultados):
        for llamada, texto in resultados:
            self.mensajes.append({"role": "tool", "tool_call_id": llamada.id, "content": texto})


class Claude:
    def __init__(self, sistema: str, pregunta: str, herramientas):
        self.cliente = AsyncAnthropic(api_key=API_KEY, base_url=BASE_URL)
        self.tools = [
            {"name": t.name, "description": t.description or "", "input_schema": esquema(t)}
            for t in herramientas
        ]
        # Claude procesa tools -> system -> mensajes. La marca en el system guarda en caché
        # herramientas + instrucciones + estructura de la base para las siguientes preguntas.
        self.sistema = [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}]
        self.mensajes = [{"role": "user", "content": pregunta}]
        self.uso = {"entrada": 0, "salida": 0, "cache": 0}

    async def turno(self):
        params = dict(
            model=MODEL,
            max_tokens=16000,
            system=self.sistema,
            tools=self.tools,
            messages=self.mensajes,
            cache_control={"type": "ephemeral"},  # además cachea la conversación entre vueltas
        )
        if MODEL in CLAUDE_CON_RESPALDO and not BASE_URL:
            # Si el modelo rechaza la consulta, la API la reintenta sola con otro modelo
            r = await self.cliente.beta.messages.create(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            r = await self.cliente.messages.create(**params)

        u = r.usage
        cache_leida = u.cache_read_input_tokens or 0
        self.uso["entrada"] += u.input_tokens + cache_leida + (u.cache_creation_input_tokens or 0)
        self.uso["salida"] += u.output_tokens
        self.uso["cache"] += cache_leida

        self.mensajes.append({"role": "assistant", "content": r.content})  # completo, sin recortar
        if r.stop_reason == "refusal":
            return "El modelo rechazó la consulta; intenta reformularla.", []
        texto = "".join(b.text for b in r.content if b.type == "text")
        llamadas = [Llamada(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        return texto, llamadas

    def agregar_resultados(self, resultados):
        # Todos los resultados van juntos en un solo mensaje
        self.mensajes.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": llamada.id, "content": texto}
            for llamada, texto in resultados
        ]})


PROVEEDORES = {"ollama": Ollama, "openai": OpenAI, "anthropic": Claude}


def nueva_conversacion(sistema: str, pregunta: str, herramientas):
    if PROVEEDOR not in PROVEEDORES:
        raise ValueError(
            f"LLM_PROVIDER='{PROVEEDOR}' no es válido. Usa: {', '.join(PROVEEDORES)}"
        )
    return PROVEEDORES[PROVEEDOR](sistema, pregunta, herramientas)
