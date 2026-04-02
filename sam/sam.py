"""
SAM — Interfaz de Consola
Para pruebas locales. Usa el mismo core que Telegram.

Uso:
    python sam.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ANTHROPIC_API_KEY, SOUL_FILE, AGENT_NAME
from sessions import obtener_info_sesion, eliminar_sesion
from sam_core import crear_agente


def main():
    if not ANTHROPIC_API_KEY:
        print("❌ Falta ANTHROPIC_API_KEY en .env")
        sys.exit(1)
    
    agente = crear_agente()
    session_id = "consola_test"
    info = obtener_info_sesion(session_id)
    
    print(f"""
╔══════════════════════════════════════════╗
║  {AGENT_NAME} — Modo Consola                 
║  Soul: {SOUL_FILE}
║  Mensajes previos: {info.get('turnos', 0)}
║                                          
║  salir → terminar | /info → sesión       
║  /nueva → reiniciar conversación         
╚══════════════════════════════════════════╝
    """)
    
    if info.get("turnos", 0) > 0:
        print(f"  💾 Sam recuerda {info['turnos']} mensajes anteriores.\n")
    
    while True:
        try:
            user_input = input(f"\n👤 Tú: ").strip()
            
            if not user_input:
                continue
            if user_input.lower() in ("salir", "exit", "/q"):
                print(f"\n👋 {AGENT_NAME}: ¡Hasta luego!")
                break
            if user_input == "/info":
                print(f"\n  📊 {obtener_info_sesion(session_id)}")
                continue
            if user_input == "/nueva":
                eliminar_sesion(session_id)
                print(f"\n  🗑️ Conversación reiniciada.")
                continue
            
            print(f"\n💭 {AGENT_NAME} pensando...")
            respuesta = agente.procesar(session_id, user_input)
            print(f"\n🤖 {AGENT_NAME}: {respuesta}")
            
        except KeyboardInterrupt:
            print(f"\n\n👋 {AGENT_NAME}: ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
