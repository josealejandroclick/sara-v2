"""
SAM - Smart Agent Multicanal
Configuración central.

Cada agente de seguros que uses Sam tendrá su propio .env
con sus propias credenciales. Este archivo lee esas variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API del modelo (Claude) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "claude-sonnet-4-20250514")

# --- Identidad del agente ---
AGENT_NAME = os.getenv("AGENT_NAME", "Sam")
SOUL_FILE = os.getenv("SOUL_FILE", "souls/default.md")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# --- GoHighLevel (CRM) ---
GHL_WEBHOOK_URL = os.getenv("GHL_WEBHOOK_URL", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "")

# --- Healthcare.gov API (cotizaciones) ---
HEALTHCARE_API_URL = "https://marketplace.api.healthcare.gov"

# --- Grupo de Telegram para notificaciones internas ---
NOTIFY_CHAT_ID = os.getenv("NOTIFY_CHAT_ID", "")
NOTIFY_BOT_TOKEN = os.getenv("NOTIFY_BOT_TOKEN", "")

# --- Límites ---
MAX_CONVERSATION_TURNS = 50
MAX_TOKENS_RESPONSE = 4096
