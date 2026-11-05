# Escenario en Make (lo armas tú, a mano)

Nombre sugerido: **Solicitudes CNE – Notificación**

## 1. Webhook (disparador)
1. En Make: *Create a new scenario* → `+` → **Webhooks → Custom webhook**.
2. *Add* → nombre `solicitudes-cne` → *Save*. Copia la URL y pégala en `.env` como `MAKE_WEBHOOK_URL`.
3. Deja el escenario esperando con **Run once**, y envía este JSON de prueba para que Make aprenda la estructura:

```bash
curl -X POST "PEGA_AQUI_TU_URL_DE_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"origen":"app-cne-demo","enviado":"2026-11-03T10:00:00","correo_destino":"tu@correo.cl","id":"1","ciudadano":"Ana Rojas","asunto":"Cobro excesivo en boleta de luz","categoria":"Tarifas","prioridad":"alta","estado":"pendiente","fecha_ingreso":"2026-10-12"}'
```
Make debe mostrar *Successfully determined*. Todos los campos son texto (la app los envía como string).

Este `curl` imita el JSON que envía la app (`enviar_a_make()` en `app.py`): las columnas de la tabla `solicitudes` más `origen`, `enviado` y `correo_destino`. Make no se conecta a MySQL; solo conoce los campos que llegan en el JSON. Si cambias las columnas, usa **Re-determine data structure** y envía un ejemplo nuevo.

## 2. Gmail → Send an email
- **To**: `correo_destino` (del webhook)
- **Subject**: `Solicitud #{id} recibida – {categoria}`
- **Content**: `Hola {ciudadano}, recibimos su solicitud "{asunto}" con prioridad {prioridad}. Estado actual: {estado}.`

## 3. Google Sheets → Add a row
Crea una hoja `Bitácora` con columnas: `enviado | id | ciudadano | asunto | prioridad | estado`.
Mapea cada columna con el campo del webhook del mismo nombre.

## 4. Extra de cierre: Router
Entre el webhook y los demás módulos, agrega un **Router**:
- Ruta 1 (todas): Gmail + Sheets.
- Ruta 2 con filtro `prioridad` *Equal to* `alta`: **Slack → Create a message** (o un segundo correo "URGENTE").

## 5. Activar
Cuando funcione con *Run once*, activa **Scheduling → Immediately** (interruptor ON abajo a la izquierda) para que el webhook responda sin tener el escenario abierto.

## Qué decir en clase
- *Módulo*: una pieza que hace una cosa. *Escenario*: la cadena de módulos.
- *Webhook*: una dirección web que "despierta" el escenario cuando alguien le envía datos.
- *Mapeo*: arrastrar un dato de un módulo a un campo de otro.
- Historial de ejecuciones: si algo falla, aquí se ve en qué módulo y por qué.
