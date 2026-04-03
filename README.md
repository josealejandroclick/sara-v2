# SAM — Smart Agent Multicanal

Agente de IA para ventas de seguros de salud.
Multi-canal (Telegram, WhatsApp, Webchat), multi-agente (una personalidad por marca), con follow-up automático.

Arquitectura inspirada en los patrones de [nanocode](https://github.com/1rgs/nanocode), [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) y [claw0](https://github.com/shareAI-lab/claw0).

## Arquitectura

```
                     sam_core.py (CEREBRO)
                    ┌──────────────────────┐
                    │  SamAgente           │
                    │  ├─ Soul (personalidad)│
                    │  ├─ Tools (herramientas)│
                    │  ├─ Sessions (memoria) │
                    │  └─ Agent Loop        │
                    └──────────┬───────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    telegram_bot.py      webhook_server.py      webchat.html
    TELEGRAM             WHATSAPP/GHL/SMS       LANDING PAGES
    (polling)            (HTTP POST)            (JavaScript)
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                         heartbeat.py
                    ┌──────────────────────┐
                    │  Follow-up automático │
                    │  Tareas programadas   │
                    └──────────────────────┘
```

## Estructura de archivos

```
sam/
├── sam.py              → Interfaz consola (pruebas)
├── sam_core.py         → Cerebro del agente
├── config.py           → Variables de entorno
├── sessions.py         → Memoria persistente (JSONL)
├── heartbeat.py        → Follow-up automático + Cron
├── requirements.txt
├── .env.example
├── README.md
├── channels/
│   ├── telegram_bot.py → Bot de Telegram + heartbeat
│   ├── webhook_server.py → Servidor HTTP para WhatsApp/GHL
│   └── webchat.html    → Widget embebible para landing pages
├── tools/
│   ├── cotizar.py      → Cotizar planes de salud
│   ├── registrar_lead.py → Enviar lead a GHL CRM
│   └── analizar_lead.py  → Clasificar temperatura del lead
└── souls/
    ├── default.md      → Personalidad genérica
    ├── salud_segura.md → Para Irania (Salud Segura)
    └── futuro_seguro.md → Para Yohenma (Futuro Seguro)
```

## Instalación

```bash
git clone <tu-repo> && cd sam
pip install -r requirements.txt
cp .env.example .env
nano .env  # Llenar API keys
```

## Uso

### Modo consola (probar)
```bash
python sam.py
```

### Modo Telegram
```bash
# 1. Crear bot en @BotFather
# 2. Poner el token en .env
python channels/telegram_bot.py
```

### Modo Webhook (WhatsApp/GHL)
```bash
python channels/webhook_server.py
# Escucha en http://0.0.0.0:8085/webhook
```

### Webchat (landing pages)
Servir `channels/webchat.html` y configurar `data-server` al URL del webhook server.

## Multi-agente

Cada agente de seguros tiene su propio bot con su personalidad:

```bash
# jimmy - mkaddesh
SOUL_FILE=souls/mkaddesh.md \
TELEGRAM_BOT_TOKEN=token-bot-mkaddesh \
python channels/telegram_bot.py

```

## Integración con GHL

### Recibir mensajes de WhatsApp via GHL:
1. En GHL crear Workflow con trigger "Customer Replied"
2. Agregar action "Webhook" → POST a `http://tu-servidor:8085/webhook`
3. Body:
```json
{
  "session_id": "whatsapp_{{contact.phone}}",
  "texto": "{{message.body}}",
  "nombre": "{{contact.name}}",
  "canal": "whatsapp"
}
```
4. Usar la respuesta de Sam para el siguiente step "Send Message"

### Enviar leads al CRM:
Configurar `GHL_WEBHOOK_URL` en .env con el webhook URL del workflow de GHL que recibe leads nuevos.

## Webchat en landing pages

Agregar al final del `<body>`:
```html
<script src="https://tu-cdn.com/sam-widget.js"
  data-server="https://sam.tudominio.com"
  data-agent="mkaddesh"
  data-color="#0ea5e9"
  data-desc="Tu asistente de seguros">
</script>
```

O embeber con iframe:
```html
<iframe src="https://sam.tudominio.com/webchat.html" 
  style="position:fixed;bottom:0;right:0;width:400px;height:600px;border:none;z-index:9999">
</iframe>
```

## Agregar nueva herramienta

1. Crear archivo en `tools/mi_herramienta.py`
2. Definir `TOOL_SCHEMA` (lo que Claude ve) y `ejecutar()` (lo que hace)
3. Importar en `sam_core.py` y agregar a `TOOL_SCHEMAS` y `TOOL_HANDLERS`

## Agregar nueva personalidad

1. Crear archivo en `souls/mi_marca.md`
2. Definir personalidad, reglas de negocio, cierre preferido
3. Configurar `SOUL_FILE=souls/mi_marca.md` en .env

## Agregar nuevo canal

1. Crear archivo en `channels/mi_canal.py`
2. Importar `crear_agente` y `procesar_mensaje` de `sam_core`
3. Recibir mensaje → `agente.procesar(session_id, texto)` → enviar respuesta

## Licencia

Uso privado — Clickia.
