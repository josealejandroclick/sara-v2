"""
SAM — Sessions (Memoria Persistente)

Patrón aprendido de claw0 s03:
"JSONL: append on write, replay on read. Too big? Summarize old parts."

Cada conversación se guarda en un archivo .jsonl
identificado por un session_id (que puede ser el chat_id de Telegram,
el número de WhatsApp, etc.)

Estructura del archivo:
  {"role": "user", "content": "hola", "ts": 1712000000}
  {"role": "assistant", "content": "¡Hola! ¿En qué puedo ayudarle?", "ts": 1712000001}
  ...

Compresión (claw0 s06 simplificado):
Cuando hay más de MAX_TURNS mensajes, los más viejos se resumen
en un solo bloque y se mantienen los recientes completos.
"""

import json
import os
import time
from pathlib import Path

# Directorio donde se guardan las sesiones
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "data/sessions")

# Máximo de turnos antes de comprimir
MAX_TURNS = 40

# Turnos recientes que se mantienen completos después de comprimir
KEEP_RECENT = 16


def _session_path(session_id: str) -> Path:
    """Ruta del archivo de sesión."""
    path = Path(SESSIONS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    # Sanitizar el session_id para usar como nombre de archivo
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    return path / f"{safe_id}.jsonl"


def cargar_sesion(session_id: str) -> list:
    """
    Lee todos los mensajes de una sesión desde disco.
    Devuelve una lista de mensajes en formato Anthropic API.
    
    Si no existe la sesión, devuelve lista vacía (usuario nuevo).
    """
    archivo = _session_path(session_id)
    
    if not archivo.exists():
        return []
    
    mensajes = []
    with open(archivo, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                registro = json.loads(linea)
                # Reconstruir en formato Anthropic API
                msg = {
                    "role": registro["role"],
                    "content": registro["content"]
                }
                mensajes.append(msg)
            except (json.JSONDecodeError, KeyError):
                continue  # Saltar líneas corruptas
    
    return mensajes


def guardar_mensaje(session_id: str, role: str, content) -> None:
    """
    Append-only: agrega UN mensaje al final del archivo.
    
    content puede ser:
    - str (texto normal)
    - list (bloques de tool_use/tool_result de la API de Anthropic)
    """
    archivo = _session_path(session_id)
    
    # Serializar content si es una lista de bloques
    if isinstance(content, list):
        content_serializable = []
        for bloque in content:
            if hasattr(bloque, "to_dict"):
                content_serializable.append(bloque.to_dict())
            elif hasattr(bloque, "model_dump"):
                content_serializable.append(bloque.model_dump())
            elif isinstance(bloque, dict):
                content_serializable.append(bloque)
            else:
                content_serializable.append(str(bloque))
        content_guardado = content_serializable
    else:
        content_guardado = content
    
    registro = {
        "role": role,
        "content": content_guardado,
        "ts": time.time()
    }
    
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def contar_turnos(session_id: str) -> int:
    """Cuenta cuántos mensajes tiene la sesión."""
    archivo = _session_path(session_id)
    if not archivo.exists():
        return 0
    with open(archivo, "r", encoding="utf-8") as f:
        return sum(1 for linea in f if linea.strip())


def necesita_compresion(session_id: str) -> bool:
    """¿La sesión tiene demasiados mensajes?"""
    return contar_turnos(session_id) > MAX_TURNS


def comprimir_sesion(session_id: str, client, model: str, system_prompt: str) -> None:
    """
    Compresión de contexto (patrón claw0 s06 simplificado):
    
    1. Carga todos los mensajes
    2. Toma los mensajes viejos (todo menos los KEEP_RECENT últimos)
    3. Le pide a Claude que haga un resumen
    4. Reescribe el archivo: resumen + mensajes recientes
    
    Esto permite conversaciones infinitas sin que se llene el contexto.
    """
    mensajes = cargar_sesion(session_id)
    
    if len(mensajes) <= KEEP_RECENT:
        return  # Nada que comprimir
    
    # Separar viejos y recientes
    mensajes_viejos = mensajes[:-KEEP_RECENT]
    mensajes_recientes = mensajes[-KEEP_RECENT:]
    
    # Construir texto de los mensajes viejos para resumir
    texto_para_resumir = ""
    for msg in mensajes_viejos:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            texto_para_resumir += f"{role}: {content}\n"
        elif isinstance(content, list):
            # Extraer texto de bloques
            for bloque in content:
                if isinstance(bloque, dict):
                    if bloque.get("type") == "text":
                        texto_para_resumir += f"{role}: {bloque.get('text', '')}\n"
                    elif bloque.get("type") == "tool_use":
                        texto_para_resumir += f"{role}: [usó herramienta {bloque.get('name', '')}]\n"
                    elif bloque.get("type") == "tool_result":
                        texto_para_resumir += f"{role}: [resultado de herramienta]\n"
    
    # Pedir resumen a Claude
    try:
        resumen_response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=(
                "Eres un asistente que resume conversaciones. "
                "Resume la siguiente conversación entre un asistente de seguros y un prospecto. "
                "Incluye: nombre del prospecto, datos que dio (ZIP, edades, ingreso), "
                "planes cotizados, nivel de interés, y cualquier detalle importante. "
                "Sé conciso pero no pierdas datos clave."
            ),
            messages=[{
                "role": "user",
                "content": f"Resume esta conversación:\n\n{texto_para_resumir}"
            }]
        )
        
        resumen_texto = resumen_response.content[0].text
        
    except Exception as e:
        print(f"  ⚠️ Error al comprimir sesión: {e}")
        return  # No comprimir si falla, mejor mantener todo
    
    # Reescribir el archivo: resumen como primer mensaje + recientes
    archivo = _session_path(session_id)
    
    with open(archivo, "w", encoding="utf-8") as f:
        # Escribir resumen como contexto del sistema inyectado
        resumen_msg = {
            "role": "user",
            "content": f"[CONTEXTO PREVIO DE ESTA CONVERSACIÓN]\n{resumen_texto}\n[FIN DEL CONTEXTO PREVIO]",
            "ts": time.time(),
            "compressed": True
        }
        f.write(json.dumps(resumen_msg, ensure_ascii=False) + "\n")
        
        # Respuesta del asistente confirmando que tiene el contexto
        ack_msg = {
            "role": "assistant",
            "content": "Entendido, tengo el contexto de nuestra conversación anterior. Continuemos.",
            "ts": time.time(),
            "compressed": True
        }
        f.write(json.dumps(ack_msg, ensure_ascii=False) + "\n")
        
        # Escribir mensajes recientes
        for msg in mensajes_recientes:
            registro = {
                "role": msg["role"],
                "content": msg["content"],
                "ts": time.time()
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    
    comprimidos = len(mensajes_viejos)
    print(f"  📦 Sesión comprimida: {comprimidos} mensajes → resumen + {KEEP_RECENT} recientes")


def obtener_info_sesion(session_id: str) -> dict:
    """Devuelve información sobre una sesión (para debugging)."""
    archivo = _session_path(session_id)
    if not archivo.exists():
        return {"existe": False, "session_id": session_id}
    
    turnos = contar_turnos(session_id)
    tamaño = archivo.stat().st_size
    
    return {
        "existe": True,
        "session_id": session_id,
        "turnos": turnos,
        "tamaño_bytes": tamaño,
        "tamaño_kb": round(tamaño / 1024, 1),
        "necesita_compresion": turnos > MAX_TURNS,
        "archivo": str(archivo)
    }


def eliminar_sesion(session_id: str) -> bool:
    """Elimina una sesión (para cuando el lead se convierte o se descarta)."""
    archivo = _session_path(session_id)
    if archivo.exists():
        archivo.unlink()
        return True
    return False
