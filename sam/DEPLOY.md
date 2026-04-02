# Desplegar Sam en Coolify — Paso a Paso

## Antes de empezar necesitas

1. Tu VPS con Coolify funcionando (ya lo tienes: srv1286303)
2. Una API key de Anthropic (la misma que usas para Sara)
3. Un bot de Telegram creado en @BotFather

---

## Paso 1: Crear el bot de Telegram

Abre Telegram, busca @BotFather y escríbele:

```
/newbot
```

Te pide un nombre → ponle: `Sam Salud Segura` (o el nombre que quieras)
Te pide un username → ponle: `saludsegura_sam_bot` (tiene que terminar en _bot)

BotFather te da un token tipo:
```
7123456789:AAH_algo_largo_aqui
```

Guárdalo. Ese es tu `TELEGRAM_BOT_TOKEN`.

---

## Paso 2: Subir Sam a GitHub

Desde tu PC, crea un repo privado y sube los archivos:

```bash
# Descomprimir el archivo que descargaste
tar -xzf sam-con-crm.tar.gz
cd sam

# Inicializar git
git init
git add .
git commit -m "Sam v1.0"

# Crear repo en GitHub (privado)
# Ve a github.com/new → nombre: sam → Private → Create
# Luego:
git remote add origin https://github.com/josealejandroclick/sam.git
git branch -M main
git push -u origin main
```

---

## Paso 3: Crear el servicio en Coolify

1. Entra a tu panel de Coolify
2. Click en **+ New Resource**
3. Selecciona **Docker Compose** o **Dockerfile** (elige Dockerfile)
4. Conecta tu repo de GitHub: `josealejandroclick/sam`
5. Branch: `main`
6. Dockerfile path: `Dockerfile`

---

## Paso 4: Configurar variables de entorno

En Coolify, ve a la sección **Environment Variables** del servicio y agrega:

```
ANTHROPIC_API_KEY=sk-ant-tu-clave-de-claude
MODEL_ID=claude-sonnet-4-20250514
AGENT_NAME=Sam
SOUL_FILE=souls/salud_segura.md
TELEGRAM_BOT_TOKEN=7123456789:AAH_tu_token_de_botfather
SESSIONS_DIR=data/sessions
HEARTBEAT_INTERVAL=300
FOLLOWUP_HOURS=24
MAX_FOLLOWUPS=3
```

**Para las notificaciones al equipo** (opcional pero recomendado):
Necesitas el chat_id del grupo de Telegram donde quieres recibir alertas de leads.
Para obtenerlo: agrega @RawDataBot al grupo, te dice el chat_id (un número negativo).

```
NOTIFY_BOT_TOKEN=7123456789:AAH_tu_token_de_botfather
NOTIFY_CHAT_ID=-1001234567890
```

**Para conectar con GHL** (opcional):
```
GHL_WEBHOOK_URL=https://services.leadconnectorhq.com/hooks/tu-webhook-id
```

---

## Paso 5: Configurar volumen persistente

IMPORTANTE: Sin esto, Sam pierde todas las conversaciones cada vez que se reinicia.

En Coolify, sección **Storages/Volumes**:

```
Source: sam-data
Destination: /app/data
```

Esto crea un volumen Docker que persiste aunque el container se reinicie.

---

## Paso 6: Configurar puerto (solo si usas webhook)

Si solo usas Telegram, no necesitas exponer puertos — Telegram usa polling (Sam llama a Telegram, no al revés).

Si también quieres el webhook server (para webchat o futuro WhatsApp):

En Coolify, sección **Network**:
- Puerto del container: `8085`
- Dominio: `sam.noxosolutions.com` (o el subdominio que quieras)
- HTTPS: activar

Para esto necesitas cambiar el CMD para correr ambos servicios. Crea este archivo:

```bash
# start.sh — Arranca Telegram + Webhook juntos
#!/bin/bash
python channels/webhook_server.py &
python channels/telegram_bot.py
```

Y en el Dockerfile cambia el CMD a:
```
CMD ["bash", "start.sh"]
```

---

## Paso 7: Deploy

Click **Deploy** en Coolify. Espera 1-2 minutos.

Revisa los logs en Coolify. Deberías ver:

```
╔══════════════════════════════════════════╗
║  Sam — Telegram + Heartbeat
║  Soul: souls/salud_segura.md
║  Modelo: claude-sonnet-4-20250514
║  Heartbeat: activo
║  Bot listo. Esperando mensajes...
╚══════════════════════════════════════════╝
```

---

## Paso 8: Probar

1. Abre Telegram
2. Busca tu bot por el username que le pusiste
3. Escribe `/start`
4. Sam debería saludarte
5. Escribe: "Hola, necesito seguro de salud, vivo en el 80202 y somos 3 personas"
6. Sam debería empezar a recopilar datos y eventualmente cotizar

---

## Para agregar un segundo agente (Yohenma / Futuro Seguro)

Repite los pasos 1-7 pero con:

- Nuevo bot en BotFather (username diferente)
- Nuevo servicio en Coolify (puedes duplicar el existente)
- Cambiar las variables:
  ```
  AGENT_NAME=Sam
  SOUL_FILE=souls/futuro_seguro.md
  TELEGRAM_BOT_TOKEN=token-del-nuevo-bot
  ```

Cada agente es un container independiente en Coolify, con su propio bot y su propia personalidad.

---

## Troubleshooting

**Sam no responde en Telegram:**
- Revisa logs en Coolify → ¿hay error de API key?
- ¿El TELEGRAM_BOT_TOKEN es correcto?
- ¿El bot está corriendo? (debe verse el mensaje de "Bot listo")

**Sam responde pero no cotiza:**
- Verifica que ANTHROPIC_API_KEY es válida
- Revisa si hay errores en los logs cuando intenta usar herramientas

**Las conversaciones se pierden al reiniciar:**
- ¿Configuraste el volumen persistente? (Paso 5)
- En logs: ¿aparece el directorio data/sessions?

**Quiero ver las conversaciones guardadas:**
- En Coolify, abre terminal del container
- `ls data/sessions/` → verás archivos .jsonl por cada chat
- `cat data/sessions/CHAT_ID.jsonl` → ves el historial

---

## Costos mensuales estimados

- VPS (ya lo tienes): $0 extra
- API de Claude: ~$5-15/mes por agente (depende del volumen de chats)
- Telegram: $0
- Total por agente: ~$5-15/mes de costo operativo

Con un precio de $300-500/mes por agente, tu margen es del 95%+.
