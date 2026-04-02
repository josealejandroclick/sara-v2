"""
SAM — Canal Telegram + Heartbeat
Etapa 4: Bot proactivo que hace follow-up automático

Ahora el bot:
1. Responde mensajes (como antes)
2. Arranca un heartbeat que cada 5 min revisa:
   - Leads sin responder → envía follow-up
   - Tareas programadas vencidas → ejecuta
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

from config import (
    TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY,
    MODEL_ID, SOUL_FILE, AGENT_NAME
)
from sessions import obtener_info_sesion, eliminar_sesion
from sam_core import crear_agente, procesar_mensaje
from heartbeat import (
    Heartbeat,
    generar_mensaje_followup,
    registrar_actividad,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("sam_telegram")


# Referencia global al bot para que el heartbeat pueda enviar mensajes
_bot: Bot = None
_loop: asyncio.AbstractEventLoop = None


# ============================================================
# HANDLERS DE TELEGRAM (igual que Etapa 3)
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    nombre = update.effective_user.first_name or "amigo"
    
    # Registrar actividad para el heartbeat
    registrar_actividad(chat_id)
    
    await update.message.reply_text(
        f"¡Hola {nombre}! 👋\n\n"
        f"Soy {AGENT_NAME}, tu asistente de seguros de salud.\n\n"
        f"Estoy aquí para ayudarte a encontrar el mejor plan de salud "
        f"para ti y tu familia. ¿En qué puedo ayudarte?\n\n"
        f"Puedes escribirme en español con confianza. 😊"
    )
    logger.info(f"Nuevo usuario: {nombre} (chat_id: {chat_id})")


async def cmd_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    eliminar_sesion(chat_id)
    await update.message.reply_text(
        "🔄 ¡Conversación reiniciada!\n¿En qué puedo ayudarle hoy?"
    )


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    info = obtener_info_sesion(chat_id)
    await update.message.reply_text(
        f"📊 Sesión:\n"
        f"Mensajes: {info.get('turnos', 0)}\n"
        f"Tamaño: {info.get('tamaño_kb', 0)} KB"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    texto = update.message.text
    nombre = update.effective_user.first_name or "Usuario"
    
    if not texto:
        return
    
    logger.info(f"[{chat_id}] {nombre}: {texto[:50]}...")
    
    await update.effective_chat.send_action(ChatAction.TYPING)
    
    try:
        agente = crear_agente()
        respuesta = procesar_mensaje(agente, chat_id, texto)
        
        if len(respuesta) <= 4096:
            await update.message.reply_text(respuesta)
        else:
            for i in range(0, len(respuesta), 4096):
                await update.message.reply_text(respuesta[i:i + 4096])
        
        logger.info(f"[{chat_id}] Sam respondió ({len(respuesta)} chars)")
        
    except Exception as e:
        logger.error(f"[{chat_id}] Error: {e}", exc_info=True)
        await update.message.reply_text(
            "Disculpe, tuve un problema técnico. "
            "¿Podría intentar de nuevo? 🙏"
        )


# ============================================================
# CALLBACKS DEL HEARTBEAT
# Estas funciones se ejecutan cuando el heartbeat detecta trabajo
# ============================================================

def _enviar_async(chat_id: str, texto: str):
    """Envía un mensaje de Telegram desde un hilo no-async."""
    if _bot and _loop:
        future = asyncio.run_coroutine_threadsafe(
            _bot.send_message(chat_id=int(chat_id), text=texto),
            _loop
        )
        try:
            future.result(timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje a {chat_id}: {e}")


def on_followup(session_id: str, followup_num: int):
    """
    Callback del heartbeat: enviar follow-up a un lead inactivo.
    
    En vez de pasar por el agent loop (que costaría tokens),
    usamos templates predefinidos. Simple, barato y efectivo.
    """
    mensaje = generar_mensaje_followup(followup_num, AGENT_NAME)
    
    logger.info(f"💓 Enviando follow-up #{followup_num} a {session_id}")
    _enviar_async(session_id, mensaje)


def on_cron(tarea: dict):
    """
    Callback del heartbeat: ejecutar tarea programada.
    
    Dependiendo del tipo de tarea:
    - recordatorio → enviar mensaje al lead
    - notificacion → enviar al grupo del equipo
    - followup → enviar follow-up personalizado
    """
    session_id = tarea.get("session_id", "")
    tipo = tarea.get("tipo", "")
    descripcion = tarea.get("descripcion", "")
    
    logger.info(f"⏰ Ejecutando cron: {tipo} - {descripcion}")
    
    if tipo == "recordatorio" and session_id:
        _enviar_async(
            session_id,
            f"⏰ Recordatorio: {descripcion}\n\n"
            f"¿Hay algo en lo que pueda ayudarle?"
        )
    
    elif tipo == "followup" and session_id:
        # Follow-up personalizado via agent loop (usa tokens pero es más natural)
        try:
            agente = crear_agente()
            respuesta = procesar_mensaje(
                agente, session_id,
                f"[SISTEMA: Envía un mensaje de follow-up. Contexto: {descripcion}]"
            )
            _enviar_async(session_id, respuesta)
        except Exception as e:
            logger.error(f"Error en cron followup: {e}")
    
    elif tipo == "notificacion":
        from config import NOTIFY_CHAT_ID
        if NOTIFY_CHAT_ID:
            _enviar_async(NOTIFY_CHAT_ID, f"📋 Tarea programada: {descripcion}")


# ============================================================
# ARRANQUE
# ============================================================

def main():
    global _bot, _loop
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Falta TELEGRAM_BOT_TOKEN en .env")
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        print("❌ Falta ANTHROPIC_API_KEY en .env")
        sys.exit(1)
    
    print(f"""
╔══════════════════════════════════════════╗
║  {AGENT_NAME} — Telegram + Heartbeat        
║  Soul: {SOUL_FILE}
║  Modelo: {MODEL_ID}
║  Heartbeat: activo                       
║  Bot listo. Esperando mensajes...        
╚══════════════════════════════════════════╝
    """)
    
    # Crear aplicación
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Guardar referencia al bot y event loop
    _bot = app.bot
    
    # Registrar handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("nueva", cmd_nueva))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Arrancar heartbeat
    heartbeat = Heartbeat(
        on_followup=on_followup,
        on_cron=on_cron
    )
    
    # Iniciar heartbeat después de que el event loop esté corriendo
    async def post_init(application):
        global _loop
        _loop = asyncio.get_event_loop()
        heartbeat.iniciar()
        logger.info("💓 Heartbeat iniciado")
    
    app.post_init = post_init
    
    # Correr
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        heartbeat.detener()


if __name__ == "__main__":
    main()
