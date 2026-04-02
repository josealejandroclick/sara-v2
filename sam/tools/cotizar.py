"""
Tool: cotizar_planes
Consulta la API de Healthcare.gov Marketplace para obtener
planes de salud disponibles y sus precios.

El modelo llama esta herramienta cuando tiene:
- ZIP code
- Cantidad de personas
- Ingreso anual
- Edades de los miembros
"""

import json
import httpx
from config import HEALTHCARE_API_URL


# --- Schema que Claude ve para saber cómo llamar esta herramienta ---
TOOL_SCHEMA = {
    "name": "cotizar_planes",
    "description": (
        "Busca planes de seguro de salud disponibles y sus precios estimados. "
        "Necesita: código ZIP, ingreso anual del hogar, y lista de edades "
        "de las personas a cubrir. Devuelve 3 opciones: Básico, Medium y Full Cover."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "zip_code": {
                "type": "string",
                "description": "Código ZIP de 5 dígitos donde vive la persona"
            },
            "ingreso_anual": {
                "type": "number",
                "description": "Ingreso anual del hogar en dólares"
            },
            "edades": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Lista de edades de las personas a cubrir. Ej: [35, 32, 5]"
            }
        },
        "required": ["zip_code", "ingreso_anual", "edades"]
    }
}


def ejecutar(zip_code: str, ingreso_anual: float, edades: list) -> str:
    """
    Llama a la API de Healthcare.gov y devuelve 3 opciones de planes.
    
    En producción esto consulta la API real.
    Por ahora usamos una simulación basada en los parámetros reales
    para que puedas probar el flujo completo sin depender de la API.
    """
    try:
        # --- Paso 1: Obtener county/FIPS del ZIP ---
        # En producción: GET /api/v1/counties/by/zip/{zip_code}
        
        # --- Paso 2: Obtener planes ---  
        # En producción: POST /api/v1/plans/search con household, income, etc.
        
        # --- Simulación realista basada en parámetros ---
        num_personas = len(edades)
        edad_mayor = max(edades)
        
        # Precio base estimado (lógica simplificada pero realista)
        base_mensual = 0
        for edad in edades:
            if edad < 15:
                base_mensual += 95
            elif edad < 30:
                base_mensual += 250
            elif edad < 40:
                base_mensual += 320
            elif edad < 50:
                base_mensual += 400
            else:
                base_mensual += 550
        
        # Ajuste por subsidio (simplificado)
        fpl_threshold = 14580 + (num_personas - 1) * 5140  # FPL 2024 aprox
        ratio_fpl = ingreso_anual / fpl_threshold
        
        if ratio_fpl <= 1.5:
            subsidio_pct = 0.85
        elif ratio_fpl <= 2.5:
            subsidio_pct = 0.70
        elif ratio_fpl <= 4.0:
            subsidio_pct = 0.50
        else:
            subsidio_pct = 0.0
        
        precio_basico = round(base_mensual * (1 - subsidio_pct) * 0.6, 2)
        precio_medium = round(base_mensual * (1 - subsidio_pct) * 0.8, 2)
        precio_full = round(base_mensual * (1 - subsidio_pct), 2)
        
        # Asegurar precios mínimos realistas
        precio_basico = max(precio_basico, 25.0)
        precio_medium = max(precio_medium, 50.0)
        precio_full = max(precio_full, 85.0)
        
        resultado = {
            "exito": True,
            "zip_code": zip_code,
            "personas_cubiertas": num_personas,
            "subsidio_estimado": f"{subsidio_pct * 100:.0f}%",
            "planes": [
                {
                    "nombre": "Plan Básico",
                    "precio_mensual": precio_basico,
                    "deducible": 7500 if subsidio_pct < 0.5 else 3000,
                    "copago_doctor": 40,
                    "cobertura": "Consultas básicas, emergencias, medicamentos genéricos",
                    "ideal_para": "Personas jóvenes y saludables que buscan protección esencial"
                },
                {
                    "nombre": "Plan Medium",
                    "precio_mensual": precio_medium,
                    "deducible": 4000 if subsidio_pct < 0.5 else 1500,
                    "copago_doctor": 25,
                    "cobertura": "Todo lo del básico + especialistas, laboratorios, maternidad",
                    "ideal_para": "Familias que necesitan cobertura regular"
                },
                {
                    "nombre": "Plan Full Cover",
                    "precio_mensual": precio_full,
                    "deducible": 1500 if subsidio_pct < 0.5 else 500,
                    "copago_doctor": 10,
                    "cobertura": "Cobertura completa: dental, visión, mental, hospitalización",
                    "ideal_para": "Quien quiere la mejor protección sin sorpresas"
                }
            ],
            "nota": "Precios estimados. El precio final depende de la verificación con el agente."
        }
        
        return json.dumps(resultado, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "exito": False,
            "error": f"Error al cotizar: {str(e)}",
            "mensaje": "No pudimos obtener precios en este momento. El agente puede ayudarle directamente."
        }, ensure_ascii=False)
