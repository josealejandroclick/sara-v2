"""
Tool: analizar_lead
Analiza la conversación y clasifica la temperatura del lead.
Envía notificación al grupo de Telegram del equipo.

Igual que Sara hace hoy, pero como herramienta modular.
"""

import json
import httpx
from config import NOTIFY_CHAT_ID, NOTIFY_BOT_TOKEN


TOOL_SCHEMA = {
    "name": "analizar_lead",
    "description": (
        "Analiza la conversación actual y clasifica al prospecto como "
        "CALIENTE (listo para comprar), TIBIO (interesado pero con dudas), "
        "o FRÍO (solo explorando). Envía notificación al equipo de ventas. "
        "Usar cuando la conversación tenga suficiente contexto para evaluar intención."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "temperatura": {
                "type": "string",
                "enum": ["CALIENTE", "TIBIO", "FRIO"],
                "description": "Clasificación del lead basada en la conversación"
            },
            "nombre_lead": {
                "type": "string",
                "description": "Nombre del prospecto"
            },
            "razon": {
                "type": "string",
                "description": "Breve explicación de por qué se clasifica así"
            },
            "accion_sugerida": {
                "type": "string",
                "description": "Qué debería hacer el agente: llamar ya, enviar info, esperar, etc."
            },
            "plan_interes": {
                "type": "string",
                "description": "Plan que mostró interés, si aplica"
            }
        },
        "required": ["temperatura", "nombre_lead", "razon", "accion_sugerida"]
    }
}


def ejecutar(
    temperatura: str,
    nombre_lead: str,
    razon: str,
    accion_sugerida: str,
    plan_interes: str = ""
) -> str:
    """
    Clasifica el lead y notifica al equipo via Telegram.
    """
    # Emojis por temperatura
    emoji_map = {
        "CALIENTE": "🔥",
        "TIBIO": "🌤️",
        "FRIO": "❄️"
    }
    emoji = emoji_map.get(temperatura, "❓")
    
    # Construir mensaje de notificación
    notificacion = (
        f"{emoji} LEAD {temperatura} {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 {nombre_lead}\n"
        f"📊 Análisis: {razon}\n"
    )
    if plan_interes:
        notificacion += f"📋 Interés: {plan_interes}\n"
    notificacion += (
        f"⚡ Acción: {accion_sugerida}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    # --- Envío real a Telegram ---
    if NOTIFY_BOT_TOKEN and NOTIFY_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
            httpx.post(url, json={
                "chat_id": NOTIFY_CHAT_ID,
                "text": notificacion,
                "parse_mode": "HTML"
            }, timeout=5.0)
        except Exception:
            pass  # No bloquear el flujo si falla la notificación
    
    return json.dumps({
        "exito": True,
        "temperatura": temperatura,
        "notificacion_enviada": bool(NOTIFY_BOT_TOKEN and NOTIFY_CHAT_ID),
        "mensaje": f"Lead clasificado como {temperatura}. Equipo notificado."
    }, ensure_ascii=False)
