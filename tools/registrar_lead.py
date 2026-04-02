"""
Tool: registrar_lead
Envía la información del lead al CRM (GoHighLevel) via webhook.

El modelo llama esta herramienta cuando tiene suficiente información
del prospecto para registrarlo.
"""

import json
import httpx
from config import GHL_WEBHOOK_URL


TOOL_SCHEMA = {
    "name": "registrar_lead",
    "description": (
        "Registra un nuevo prospecto en el sistema del agente de seguros. "
        "Usar cuando se tiene nombre, teléfono y al menos el ZIP code del prospecto. "
        "También puede incluir información de la cotización si ya se hizo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre": {
                "type": "string",
                "description": "Nombre completo del prospecto"
            },
            "telefono": {
                "type": "string",
                "description": "Número de teléfono del prospecto"
            },
            "zip_code": {
                "type": "string",
                "description": "Código ZIP donde vive"
            },
            "ingreso_anual": {
                "type": "number",
                "description": "Ingreso anual del hogar (si lo dio)"
            },
            "num_personas": {
                "type": "integer",
                "description": "Cantidad de personas a cubrir"
            },
            "plan_interes": {
                "type": "string",
                "description": "Plan que le interesó: Básico, Medium o Full Cover"
            },
            "notas": {
                "type": "string",
                "description": "Cualquier nota adicional relevante sobre el prospecto"
            }
        },
        "required": ["nombre", "telefono"]
    }
}


def ejecutar(
    nombre: str,
    telefono: str,
    zip_code: str = "",
    ingreso_anual: float = 0,
    num_personas: int = 0,
    plan_interes: str = "",
    notas: str = ""
) -> str:
    """
    Envía el lead a GHL via webhook.
    En modo desarrollo, simula el envío.
    """
    payload = {
        "nombre": nombre,
        "telefono": telefono,
        "zip_code": zip_code,
        "ingreso_anual": ingreso_anual,
        "num_personas": num_personas,
        "plan_interes": plan_interes,
        "notas": notas,
        "fuente": "sam_bot"
    }
    
    # --- Envío real a GHL ---
    if GHL_WEBHOOK_URL:
        try:
            response = httpx.post(
                GHL_WEBHOOK_URL,
                json=payload,
                timeout=10.0
            )
            if response.status_code == 200:
                return json.dumps({
                    "exito": True,
                    "mensaje": f"Lead {nombre} registrado exitosamente en el CRM."
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "exito": False,
                    "mensaje": "Error al registrar. El agente lo registrará manualmente."
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "exito": False,
                "mensaje": f"Error de conexión: {str(e)}"
            }, ensure_ascii=False)
    
    # --- Modo desarrollo (sin webhook configurado) ---
    return json.dumps({
        "exito": True,
        "modo": "desarrollo",
        "mensaje": f"Lead {nombre} preparado para registro. (Webhook no configurado)",
        "datos": payload
    }, ensure_ascii=False, indent=2)
