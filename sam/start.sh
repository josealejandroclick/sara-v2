#!/bin/bash
# SAM — Script de arranque
# Corre el bot de Telegram y el webhook server en paralelo

echo "=== Iniciando Sam ==="

# Arrancar webhook server en background (para webchat)
python channels/webhook_server.py &
WEBHOOK_PID=$!
echo "Webhook server iniciado (PID: $WEBHOOK_PID)"

# Arrancar bot de Telegram en foreground
python channels/telegram_bot.py

# Si Telegram se cae, matar webhook también
kill $WEBHOOK_PID 2>/dev/null
