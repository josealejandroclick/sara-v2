"""
Sara — Configuración central.
Cada despliegue tiene su propio .env con sus credenciales.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Claude API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "claude-opus-4-5")

# --- Identidad ---
AGENT_NAME = os.getenv("AGENT_NAME", "Sara")
SOUL_FILE = os.getenv("SOUL_FILE", "souls/sara_mkaddesh.md")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# --- GoHighLevel CRM ---
GHL_WEBHOOK_URL = os.getenv("GHL_WEBHOOK_URL", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "")

# --- Healthcare.gov API ---
HEALTHCARE_API_URL = "https://marketplace.api.healthcare.gov"
HEALTHCARE_API_KEY = os.getenv("HEALTHCARE_API_KEY", "XIvzGUQ5RSDAAqGFukLxcmrJ8P2zcCik")

# --- Google Maps API ---
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# --- Notificaciones al grupo ---
NOTIFY_CHAT_ID = os.getenv("NOTIFY_CHAT_ID", "")
NOTIFY_BOT_TOKEN = os.getenv("NOTIFY_BOT_TOKEN", "")

# --- Sessions ---
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "data/sessions")

# --- Límites ---
MAX_CONVERSATION_TURNS = 50
MAX_TOKENS_RESPONSE = 4096
