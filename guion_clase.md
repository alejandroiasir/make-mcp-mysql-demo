# Guion de clase: Make + Python + MCP (60 min, principiantes)

## Preparación (antes de la clase)
- [ ] Instalar MySQL: `brew install mysql && brew services start mysql`
- [ ] Cargar datos: `mysql -u root < schema.sql` (cambia antes la clave de `cne_lector` en `schema.sql` y usa la misma en `.env`)
- [ ] `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- [ ] Descargar el modelo local una sola vez: `ollama pull qwen3:8b` (~5 GB). Ollama debe estar abierto durante la clase
- [ ] Copiar `.env.example` a `.env` y completar `MAKE_WEBHOOK_URL` (el modelo local no usa API key)
- [ ] Armar y probar el escenario con `make_escenario.md`, y dejarlo **activado**
- [ ] Ensayo completo: `streamlit run app.py`
- [ ] Tener a mano una captura o video del resultado (Plan B)

## Minuto a minuto
| Min | Qué hacer | Frase clave |
|---|---|---|
| 0–10 | Slides o pizarra: trigger → módulos → resultado. Ejemplo: "cuando llega un correo, guardo el adjunto en Drive" | "Make conecta aplicaciones sin escribir código" |
| 10–25 | Crear el escenario en vivo (webhook → Gmail → Sheets) y probar con el `curl` | "El webhook es una dirección que despierta al escenario" |
| 25–45 | Mostrar `app.py`: preguntar en lenguaje natural, ver la tabla, pulsar *Enviar a Make*, mostrar el correo y la fila | "La IA entiende el dato, Make decide qué pasa después" |
| 45–50 | Añadir el Router (`prioridad = alta`) y enviar una solicitud alta y otra baja | "Un filtro es una condición: si se cumple, sigue" |
| 50–55 | Ahorro de tokens: mostrar el contador de tokens, el panel "Contexto de la base" y una consulta frecuente sin IA | "El modelo no lee la base entera: solo ve el mapa y un resumen" |
| 55–60 | Ideas para su área, preguntas | "Busquen una tarea repetitiva que hagan cada semana" |

## Preguntas de ejemplo para la demo
- "Muéstrame las solicitudes de prioridad alta que siguen pendientes"
- "Muéstrame las solicitudes de categoría electricidad que siguen pendientes"
- "Muéstrame las solicitudes que están resueltas"
- "Muéstrame las solicitudes que están con prioridad media"
- "¿Cuáles son las solicitudes que están en_proceso?"
- "¿Cuántas solicitudes hay por categoría?" (el modelo debería usar `COUNT ... GROUP BY`)

## Si algo falla
- Falla el modelo: usa **Consultas frecuentes → Ejecutar sin IA** en la barra lateral.
- Falla MySQL: botón **Usar datos de ejemplo (Plan B)**; el envío a Make sigue funcionando.
- No llega el correo: revisa el historial de ejecuciones del escenario en Make.
- Error de MCP: probar `npx -y @benborla29/mcp-server-mysql` con las variables `MYSQL_*` para ver el mensaje.

## Recordatorio de seguridad
Solo datos ficticios. El usuario `cne_lector` es de solo lectura. No muestres el `.env` en pantalla.
