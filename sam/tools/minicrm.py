"""
Tool: minicrm
CRM minimalista embebido en Sam.
Reemplaza las funciones básicas de GHL sin costo adicional.

Capacidades:
- Crear/editar/buscar contactos
- Mover contactos por etapas del pipeline
- Registrar actividades y notas
- Listar pipeline por etapa
- Estadísticas básicas

Almacenamiento: JSON en disco (data/crm/)
Sin base de datos, sin setup, sin costo.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime

CRM_DIR = os.path.join(os.getenv("SESSIONS_DIR", "data"), "crm")
CONTACTS_FILE = os.path.join(CRM_DIR, "contacts.json")

# Etapas del pipeline
PIPELINE_STAGES = [
    "nuevo",
    "contactado",
    "cotizado",
    "negociando",
    "ganado",
    "perdido"
]


# ============================================================
# STORAGE
# ============================================================

def _ensure_dir():
    Path(CRM_DIR).mkdir(parents=True, exist_ok=True)

def _load_contacts() -> dict:
    _ensure_dir()
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_contacts(contacts: dict):
    _ensure_dir()
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)


def _gen_id() -> str:
    return f"c_{int(time.time()*1000)}"


# ============================================================
# TOOL SCHEMAS (lo que Claude ve)
# ============================================================

TOOL_SCHEMA_CREAR = {
    "name": "crm_crear_contacto",
    "description": (
        "Crea un nuevo contacto en el CRM. Usar cuando se tiene al menos "
        "el nombre del prospecto. Opcionalmente incluir teléfono, email, "
        "notas y etapa del pipeline."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre": {"type": "string", "description": "Nombre completo"},
            "telefono": {"type": "string", "description": "Teléfono"},
            "email": {"type": "string", "description": "Email"},
            "etapa": {
                "type": "string",
                "enum": PIPELINE_STAGES,
                "description": "Etapa del pipeline (default: nuevo)"
            },
            "fuente": {"type": "string", "description": "De dónde vino: whatsapp, telegram, web, referido"},
            "notas": {"type": "string", "description": "Notas iniciales sobre el contacto"},
            "datos_extra": {
                "type": "object",
                "description": "Datos adicionales: zip_code, ingreso, edades, plan_interes, etc."
            }
        },
        "required": ["nombre"]
    }
}

TOOL_SCHEMA_BUSCAR = {
    "name": "crm_buscar_contacto",
    "description": (
        "Busca contactos en el CRM por nombre, teléfono o email. "
        "Devuelve los contactos que coincidan."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "busqueda": {
                "type": "string",
                "description": "Texto a buscar en nombre, teléfono o email"
            }
        },
        "required": ["busqueda"]
    }
}

TOOL_SCHEMA_ACTUALIZAR = {
    "name": "crm_actualizar_contacto",
    "description": (
        "Actualiza la información de un contacto existente. "
        "Puede cambiar etapa, agregar notas, actualizar datos."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string", "description": "ID del contacto"},
            "etapa": {"type": "string", "enum": PIPELINE_STAGES},
            "notas": {"type": "string", "description": "Nueva nota a agregar"},
            "telefono": {"type": "string"},
            "email": {"type": "string"},
            "datos_extra": {"type": "object", "description": "Datos adicionales a actualizar"}
        },
        "required": ["contact_id"]
    }
}

TOOL_SCHEMA_PIPELINE = {
    "name": "crm_ver_pipeline",
    "description": (
        "Muestra el pipeline completo o filtrado por etapa. "
        "Devuelve contactos agrupados por etapa con resumen."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "etapa": {
                "type": "string",
                "enum": PIPELINE_STAGES,
                "description": "Filtrar por etapa específica (omitir para ver todo)"
            }
        }
    }
}

TOOL_SCHEMA_STATS = {
    "name": "crm_estadisticas",
    "description": (
        "Devuelve estadísticas del CRM: total de contactos, "
        "contactos por etapa, tasa de conversión, actividad reciente."
    ),
    "input_schema": {
        "type": "object",
        "properties": {}
    }
}

# Lista de todos los schemas
ALL_SCHEMAS = [
    TOOL_SCHEMA_CREAR,
    TOOL_SCHEMA_BUSCAR,
    TOOL_SCHEMA_ACTUALIZAR,
    TOOL_SCHEMA_PIPELINE,
    TOOL_SCHEMA_STATS,
]


# ============================================================
# HANDLERS
# ============================================================

def crear_contacto(
    nombre: str,
    telefono: str = "",
    email: str = "",
    etapa: str = "nuevo",
    fuente: str = "",
    notas: str = "",
    datos_extra: dict = None,
    **kwargs
) -> str:
    contacts = _load_contacts()
    cid = _gen_id()
    
    ahora = datetime.now().isoformat()
    
    contact = {
        "id": cid,
        "nombre": nombre,
        "telefono": telefono,
        "email": email,
        "etapa": etapa if etapa in PIPELINE_STAGES else "nuevo",
        "fuente": fuente,
        "creado": ahora,
        "actualizado": ahora,
        "datos_extra": datos_extra or {},
        "actividades": []
    }
    
    if notas:
        contact["actividades"].append({
            "tipo": "nota",
            "contenido": notas,
            "fecha": ahora
        })
    
    contacts[cid] = contact
    _save_contacts(contacts)
    
    return json.dumps({
        "exito": True,
        "contact_id": cid,
        "mensaje": f"Contacto '{nombre}' creado en etapa '{etapa}'.",
        "contacto": contact
    }, ensure_ascii=False)


def buscar_contacto(busqueda: str, **kwargs) -> str:
    contacts = _load_contacts()
    busqueda_lower = busqueda.lower()
    
    resultados = []
    for cid, c in contacts.items():
        if (busqueda_lower in c.get("nombre", "").lower() or
            busqueda_lower in c.get("telefono", "").lower() or
            busqueda_lower in c.get("email", "").lower()):
            resultados.append(c)
    
    return json.dumps({
        "exito": True,
        "total": len(resultados),
        "contactos": resultados
    }, ensure_ascii=False)


def actualizar_contacto(
    contact_id: str,
    etapa: str = None,
    notas: str = None,
    telefono: str = None,
    email: str = None,
    datos_extra: dict = None,
    **kwargs
) -> str:
    contacts = _load_contacts()
    
    if contact_id not in contacts:
        return json.dumps({"exito": False, "error": "Contacto no encontrado"})
    
    c = contacts[contact_id]
    ahora = datetime.now().isoformat()
    
    cambios = []
    
    if etapa and etapa in PIPELINE_STAGES:
        vieja = c["etapa"]
        c["etapa"] = etapa
        cambios.append(f"Etapa: {vieja} → {etapa}")
        c["actividades"].append({
            "tipo": "cambio_etapa",
            "contenido": f"Movido de '{vieja}' a '{etapa}'",
            "fecha": ahora
        })
    
    if telefono:
        c["telefono"] = telefono
        cambios.append(f"Teléfono actualizado")
    
    if email:
        c["email"] = email
        cambios.append(f"Email actualizado")
    
    if notas:
        c["actividades"].append({
            "tipo": "nota",
            "contenido": notas,
            "fecha": ahora
        })
        cambios.append("Nota agregada")
    
    if datos_extra:
        c["datos_extra"].update(datos_extra)
        cambios.append("Datos actualizados")
    
    c["actualizado"] = ahora
    _save_contacts(contacts)
    
    return json.dumps({
        "exito": True,
        "mensaje": f"Contacto actualizado: {', '.join(cambios)}",
        "contacto": c
    }, ensure_ascii=False)


def ver_pipeline(etapa: str = None, **kwargs) -> str:
    contacts = _load_contacts()
    
    pipeline = {s: [] for s in PIPELINE_STAGES}
    
    for cid, c in contacts.items():
        stage = c.get("etapa", "nuevo")
        if stage in pipeline:
            pipeline[stage].append({
                "id": c["id"],
                "nombre": c["nombre"],
                "telefono": c.get("telefono", ""),
                "fuente": c.get("fuente", ""),
                "actualizado": c.get("actualizado", ""),
                "actividades_count": len(c.get("actividades", []))
            })
    
    if etapa and etapa in PIPELINE_STAGES:
        resultado = {etapa: pipeline[etapa]}
    else:
        resultado = pipeline
    
    resumen = {s: len(contacts_list) for s, contacts_list in pipeline.items()}
    
    return json.dumps({
        "exito": True,
        "resumen": resumen,
        "total": sum(resumen.values()),
        "pipeline": resultado
    }, ensure_ascii=False, indent=2)


def estadisticas(**kwargs) -> str:
    contacts = _load_contacts()
    
    por_etapa = {s: 0 for s in PIPELINE_STAGES}
    por_fuente = {}
    total_actividades = 0
    
    for c in contacts.values():
        etapa = c.get("etapa", "nuevo")
        if etapa in por_etapa:
            por_etapa[etapa] += 1
        
        fuente = c.get("fuente", "desconocido") or "desconocido"
        por_fuente[fuente] = por_fuente.get(fuente, 0) + 1
        
        total_actividades += len(c.get("actividades", []))
    
    total = len(contacts)
    ganados = por_etapa.get("ganado", 0)
    tasa_conversion = round((ganados / total * 100), 1) if total > 0 else 0
    
    return json.dumps({
        "exito": True,
        "total_contactos": total,
        "por_etapa": por_etapa,
        "por_fuente": por_fuente,
        "total_actividades": total_actividades,
        "tasa_conversion": f"{tasa_conversion}%",
        "activos": total - por_etapa.get("ganado", 0) - por_etapa.get("perdido", 0)
    }, ensure_ascii=False, indent=2)


# Dispatch map
ALL_HANDLERS = {
    "crm_crear_contacto": crear_contacto,
    "crm_buscar_contacto": buscar_contacto,
    "crm_actualizar_contacto": actualizar_contacto,
    "crm_ver_pipeline": ver_pipeline,
    "crm_estadisticas": estadisticas,
}
