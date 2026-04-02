"""
SAM — Heartbeat + Cron (Agente Proactivo)
Etapa 4

Patrón aprendido de claw0 s07:
"Timer thread: should I run? + queue work alongside user messages."

HEARTBEAT:
  Un hilo que se despierta cada HEARTBEAT_INTERVAL segundos.
  Revisa todas las sesiones activas buscando:
  - Leads que no respondieron en X horas → enviar follow-up
  - Leads calientes sin cita agendada → recordar al equipo
  
CRON:
  Tareas programadas con fecha/hora específica:
  - "Recordar llamar a María mañana a las 10"
  - "Enviar resumen de leads del día a las 6pm"
  
  Se guardan en un archivo JSON. El heartbeat las revisa
  en cada ciclo y ejecuta las que ya vencieron.

IMPORTANTE: El heartbeat NO responde al usuario directamente.
Encola acciones que el canal (Telegram/WhatsApp) ejecuta.
"""

import json
import os
import time
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("sam_heartbeat")

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Cada cuántos segundos se despierta el heartbeat
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "300"))  # 5 min default

# Horas sin respuesta para considerar follow-up
FOLLOWUP_HOURS = int(os.getenv("FOLLOWUP_HOURS", "24"))

# Máximo de follow-ups antes de marcar como frío
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", "3"))

# Archivos de datos
DATA_DIR = os.getenv("SESSIONS_DIR", "data/sessions")
CRON_FILE = os.path.join(os.getenv("SESSIONS_DIR", "data"), "cron_tasks.json")
FOLLOWUP_FILE = os.path.join(os.getenv("SESSIONS_DIR", "data"), "followup_tracker.json")


# ============================================================
# FOLLOW-UP TRACKER
# Rastrea cuándo fue el último mensaje de cada sesión
# y cuántos follow-ups se han enviado
# ============================================================

def _cargar_tracker() -> dict:
    """Carga el tracker de follow-ups desde disco."""
    try:
        with open(FOLLOWUP_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _guardar_tracker(tracker: dict):
    """Guarda el tracker en disco."""
    Path(os.path.dirname(FOLLOWUP_FILE)).mkdir(parents=True, exist_ok=True)
    with open(FOLLOWUP_FILE, "w") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


def registrar_actividad(session_id: str):
    """
    Marca que hubo actividad en una sesión.
    Llamar cada vez que el usuario envía un mensaje.
    Resetea el contador de follow-ups.
    """
    tracker = _cargar_tracker()
    tracker[session_id] = {
        "ultimo_mensaje": time.time(),
        "followups_enviados": 0,
        "activo": True
    }
    _guardar_tracker(tracker)


def obtener_leads_para_followup() -> list:
    """
    Revisa qué leads necesitan follow-up.
    
    Criterios:
    - Último mensaje hace más de FOLLOWUP_HOURS horas
    - Menos de MAX_FOLLOWUPS follow-ups enviados
    - Sesión marcada como activa
    
    Returns: lista de session_ids que necesitan follow-up
    """
    tracker = _cargar_tracker()
    ahora = time.time()
    umbral = ahora - (FOLLOWUP_HOURS * 3600)
    
    leads = []
    for session_id, data in tracker.items():
        if not data.get("activo", True):
            continue
        if data.get("followups_enviados", 0) >= MAX_FOLLOWUPS:
            continue
        if data.get("ultimo_mensaje", ahora) < umbral:
            leads.append(session_id)
    
    return leads


def marcar_followup_enviado(session_id: str):
    """Incrementa el contador de follow-ups enviados."""
    tracker = _cargar_tracker()
    if session_id in tracker:
        tracker[session_id]["followups_enviados"] = (
            tracker[session_id].get("followups_enviados", 0) + 1
        )
        tracker[session_id]["ultimo_followup"] = time.time()
        
        # Si llegó al máximo, desactivar
        if tracker[session_id]["followups_enviados"] >= MAX_FOLLOWUPS:
            tracker[session_id]["activo"] = False
        
        _guardar_tracker(tracker)


def desactivar_sesion(session_id: str):
    """Marca una sesión como inactiva (lead convertido o descartado)."""
    tracker = _cargar_tracker()
    if session_id in tracker:
        tracker[session_id]["activo"] = False
        _guardar_tracker(tracker)


# ============================================================
# CRON TASKS
# Tareas programadas con fecha/hora de ejecución
# ============================================================

def _cargar_cron() -> list:
    """Carga las tareas cron desde disco."""
    try:
        with open(CRON_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar_cron(tasks: list):
    """Guarda las tareas cron en disco."""
    Path(os.path.dirname(CRON_FILE)).mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def programar_tarea(
    session_id: str,
    ejecutar_en: str,
    tipo: str,
    descripcion: str,
    datos: dict = None
):
    """
    Programa una tarea para ejecutar en el futuro.
    
    Args:
        session_id: sesión asociada
        ejecutar_en: fecha/hora ISO format "2026-04-02T10:00:00"
        tipo: "followup", "recordatorio", "notificacion"
        descripcion: qué hacer
        datos: datos adicionales
    """
    tasks = _cargar_cron()
    tasks.append({
        "id": f"cron_{int(time.time())}_{session_id[:8]}",
        "session_id": session_id,
        "ejecutar_en": ejecutar_en,
        "tipo": tipo,
        "descripcion": descripcion,
        "datos": datos or {},
        "creado": datetime.now().isoformat(),
        "ejecutado": False
    })
    _guardar_cron(tasks)
    logger.info(f"Tarea programada: {tipo} para {session_id} en {ejecutar_en}")


def obtener_tareas_pendientes() -> list:
    """Devuelve tareas cuya hora de ejecución ya pasó y no se han ejecutado."""
    tasks = _cargar_cron()
    ahora = datetime.now().isoformat()
    
    pendientes = [
        t for t in tasks
        if not t.get("ejecutado", False) and t.get("ejecutar_en", "9999") <= ahora
    ]
    return pendientes


def marcar_tarea_ejecutada(task_id: str):
    """Marca una tarea cron como ejecutada."""
    tasks = _cargar_cron()
    for t in tasks:
        if t.get("id") == task_id:
            t["ejecutado"] = True
            t["ejecutado_en"] = datetime.now().isoformat()
    _guardar_cron(tasks)


# ============================================================
# TOOL SCHEMA PARA AGENDAR
# El modelo puede usar esta herramienta para programar tareas
# ============================================================

TOOL_SCHEMA = {
    "name": "agendar_tarea",
    "description": (
        "Programa una tarea futura: recordatorio de llamada, follow-up, "
        "o cualquier acción que deba ejecutarse en una fecha/hora específica. "
        "Ejemplo: 'recordar llamar a María mañana a las 10am'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ejecutar_en": {
                "type": "string",
                "description": (
                    "Fecha y hora en formato ISO: 2026-04-02T10:00:00. "
                    "Calcular basándose en la fecha actual."
                )
            },
            "tipo": {
                "type": "string",
                "enum": ["followup", "recordatorio", "notificacion"],
                "description": "Tipo de tarea"
            },
            "descripcion": {
                "type": "string",
                "description": "Qué hacer cuando llegue la hora"
            }
        },
        "required": ["ejecutar_en", "tipo", "descripcion"]
    }
}


def ejecutar_agendar(ejecutar_en: str, tipo: str, descripcion: str, **kwargs) -> str:
    """Handler de la herramienta agendar_tarea."""
    # El session_id se inyecta desde el agent loop
    session_id = kwargs.get("session_id", "unknown")
    programar_tarea(session_id, ejecutar_en, tipo, descripcion)
    return json.dumps({
        "exito": True,
        "mensaje": f"Tarea programada: {descripcion} para {ejecutar_en}"
    }, ensure_ascii=False)


# ============================================================
# HEARTBEAT ENGINE
# El hilo que se despierta periódicamente a buscar trabajo
# ============================================================

class Heartbeat:
    """
    Motor de heartbeat.
    
    Patrón claw0 s07: un timer thread que cada X segundos:
    1. Revisa leads para follow-up
    2. Revisa tareas cron pendientes
    3. Encola acciones para que el canal las ejecute
    
    No envía mensajes directamente — encola callbacks
    que el canal (Telegram/WhatsApp) ejecuta.
    """
    
    def __init__(self, on_followup: Callable = None, on_cron: Callable = None):
        """
        Args:
            on_followup: función(session_id, followup_num) que se llama
                        cuando hay que hacer follow-up a un lead
            on_cron: función(task) que se llama cuando una tarea cron vence
        """
        self.on_followup = on_followup
        self.on_cron = on_cron
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self.ciclos = 0
    
    def iniciar(self):
        """Arranca el heartbeat."""
        self._running = True
        self._programar_siguiente()
        logger.info(
            f"Heartbeat iniciado (cada {HEARTBEAT_INTERVAL}s, "
            f"follow-up después de {FOLLOWUP_HOURS}h)"
        )
    
    def detener(self):
        """Detiene el heartbeat."""
        self._running = False
        if self._timer:
            self._timer.cancel()
        logger.info(f"Heartbeat detenido después de {self.ciclos} ciclos.")
    
    def _programar_siguiente(self):
        """Programa el siguiente latido."""
        if self._running:
            self._timer = threading.Timer(HEARTBEAT_INTERVAL, self._latido)
            self._timer.daemon = True
            self._timer.start()
    
    def _latido(self):
        """
        UN latido del heartbeat.
        Se ejecuta cada HEARTBEAT_INTERVAL segundos.
        """
        self.ciclos += 1
        
        try:
            # --- 1. Revisar follow-ups ---
            leads = obtener_leads_para_followup()
            for session_id in leads:
                tracker = _cargar_tracker()
                followup_num = tracker.get(session_id, {}).get("followups_enviados", 0) + 1
                
                logger.info(f"💓 Follow-up #{followup_num} para {session_id}")
                
                if self.on_followup:
                    try:
                        self.on_followup(session_id, followup_num)
                        marcar_followup_enviado(session_id)
                    except Exception as e:
                        logger.error(f"Error en follow-up {session_id}: {e}")
            
            # --- 2. Revisar tareas cron ---
            tareas = obtener_tareas_pendientes()
            for tarea in tareas:
                logger.info(f"⏰ Ejecutando tarea cron: {tarea.get('descripcion')}")
                
                if self.on_cron:
                    try:
                        self.on_cron(tarea)
                        marcar_tarea_ejecutada(tarea["id"])
                    except Exception as e:
                        logger.error(f"Error en cron {tarea['id']}: {e}")
            
            if leads or tareas:
                logger.info(
                    f"💓 Ciclo {self.ciclos}: "
                    f"{len(leads)} follow-ups, {len(tareas)} cron tasks"
                )
                
        except Exception as e:
            logger.error(f"Error en heartbeat ciclo {self.ciclos}: {e}")
        
        # Programar siguiente latido
        self._programar_siguiente()


# ============================================================
# MENSAJES DE FOLLOW-UP
# Templates según el número de follow-up
# ============================================================

FOLLOWUP_TEMPLATES = [
    # Follow-up #1 (después de 24h)
    (
        "¡Hola! 👋 Soy {agent_name}, ¿recuerda que estuvimos hablando sobre "
        "su seguro de salud? Quería saber si le quedó alguna duda que pueda resolver. "
        "Estoy aquí para ayudarle. 😊"
    ),
    # Follow-up #2 (después de 48h)
    (
        "Hola de nuevo. Solo quería recordarle que las opciones de seguro que "
        "revisamos juntos siguen disponibles. Si quiere, puedo agendar una "
        "llamada rápida con el agente para que le explique todo sin compromiso. "
        "¿Le parece bien?"
    ),
    # Follow-up #3 (último intento)
    (
        "¡Hola! Este es mi último mensaje por ahora. Si en algún momento "
        "necesita ayuda con su seguro de salud, no dude en escribirme. "
        "Estaré aquí cuando me necesite. ¡Que tenga un excelente día! 🙏"
    ),
]


def generar_mensaje_followup(followup_num: int, agent_name: str = "Sam") -> str:
    """Genera el mensaje de follow-up según el número de intento."""
    idx = min(followup_num - 1, len(FOLLOWUP_TEMPLATES) - 1)
    return FOLLOWUP_TEMPLATES[idx].format(agent_name=agent_name)
