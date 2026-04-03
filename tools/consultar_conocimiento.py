"""
Tool: consultar_conocimiento
Carga la base de conocimiento de Sara y devuelve la sección relevante
para responder una pregunta específica del cliente.

La base de conocimiento está en knowledge/sara_knowledge.md
Para actualizarla: editar ese archivo y hacer redeploy.
"""

import json
import os
from pathlib import Path


TOOL_SCHEMA = {
    "name": "consultar_conocimiento",
    "description": (
        "Consulta la base de conocimiento interna de MKAddesh para obtener "
        "información correcta sobre: elegibilidad de productos, coberturas, "
        "restricciones, condiciones preexistentes, embarazo, estatus migratorio, "
        "metodología de venta, objeciones, o cualquier detalle de negocio. "
        "Usar SIEMPRE antes de responder preguntas sobre productos, elegibilidad "
        "o situaciones especiales del cliente."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pregunta": {
                "type": "string",
                "description": (
                    "La pregunta o tema a consultar. Ser específico. "
                    "Ejemplos: 'embarazo y cobertura suplementaria', "
                    "'elegibilidad sin documentos', 'qué cubre el plan medium', "
                    "'condiciones preexistentes período de espera'"
                )
            },
            "seccion": {
                "type": "string",
                "enum": [
                    "productos",
                    "elegibilidad",
                    "metodologia",
                    "psicologia",
                    "objeciones",
                    "lenguaje",
                    "prohibiciones",
                    "logistica",
                    "todo"
                ],
                "description": (
                    "Sección específica a consultar. Usar 'todo' si no estás seguro. "
                    "productos=coberturas y beneficios, "
                    "elegibilidad=quién califica, restricciones, preexistencias, embarazo, "
                    "metodologia=secuencia de venta, cierre, calificación, "
                    "psicologia=perfil del cliente hispano, "
                    "objeciones=respuestas a objeciones, "
                    "lenguaje=términos correctos y analogías, "
                    "prohibiciones=qué nunca decir ni hacer"
                )
            }
        },
        "required": ["pregunta"]
    }
}


# Mapeo de secciones a encabezados en el documento
SECTION_MAP = {
    "productos":     "## SECCIÓN 1",
    "elegibilidad":  "## SECCIÓN 2",
    "metodologia":   "## SECCIÓN 3",
    "psicologia":    "## SECCIÓN 4",
    "objeciones":    "## SECCIÓN 5",
    "lenguaje":      "## SECCIÓN 6",
    "prohibiciones": "## SECCIÓN 7",
    "logistica":     "## SECCIÓN 8",
    "todo":          None
}


def _cargar_knowledge() -> str:
    """Carga el archivo de conocimiento."""
    # Buscar el archivo en rutas posibles
    rutas = [
        Path(__file__).parent.parent / "knowledge" / "sara_knowledge.md",
        Path("/app/knowledge/sara_knowledge.md"),
        Path("knowledge/sara_knowledge.md"),
    ]
    for ruta in rutas:
        if ruta.exists():
            return ruta.read_text(encoding="utf-8")
    return ""


def _extraer_seccion(contenido: str, seccion: str) -> str:
    """Extrae una sección específica del documento."""
    if not seccion or seccion == "todo":
        return contenido

    encabezado = SECTION_MAP.get(seccion)
    if not encabezado:
        return contenido

    lineas = contenido.split("\n")
    dentro = False
    resultado = []

    for linea in lineas:
        if linea.startswith(encabezado):
            dentro = True
            resultado.append(linea)
            continue
        if dentro:
            # Terminar si encontramos el siguiente ## SECCIÓN
            if linea.startswith("## SECCIÓN") and linea != lineas[lineas.index(linea)]:
                break
            resultado.append(linea)

    return "\n".join(resultado).strip() if resultado else contenido


def _buscar_relevante(contenido: str, pregunta: str) -> str:
    """
    Busca párrafos relevantes para la pregunta dentro del contenido.
    Devuelve los bloques que contienen palabras clave de la pregunta.
    """
    palabras_clave = [
        p.lower() for p in pregunta.lower().split()
        if len(p) > 3 and p not in ["para", "como", "qué", "que", "una", "los", "las", "del"]
    ]

    if not palabras_clave:
        return contenido[:3000]

    bloques = contenido.split("\n\n")
    relevantes = []

    for bloque in bloques:
        bloque_lower = bloque.lower()
        coincidencias = sum(1 for palabra in palabras_clave if palabra in bloque_lower)
        if coincidencias > 0:
            relevantes.append((coincidencias, bloque))

    # Ordenar por relevancia y tomar los mejores
    relevantes.sort(key=lambda x: x[0], reverse=True)
    top = [b for _, b in relevantes[:6]]

    if top:
        return "\n\n".join(top)
    return contenido[:3000]


def ejecutar(pregunta: str, seccion: str = "todo") -> str:
    """
    Consulta la base de conocimiento y devuelve información relevante.
    """
    contenido = _cargar_knowledge()

    if not contenido:
        return json.dumps({
            "exito": False,
            "error": "Base de conocimiento no disponible",
            "respuesta": "Información no disponible en este momento. Escalar al asesor."
        }, ensure_ascii=False)

    # Extraer sección específica si se indicó
    seccion_contenido = _extraer_seccion(contenido, seccion)

    # Buscar párrafos relevantes para la pregunta
    resultado = _buscar_relevante(seccion_contenido, pregunta)

    return json.dumps({
        "exito": True,
        "pregunta": pregunta,
        "seccion_consultada": seccion,
        "informacion": resultado
    }, ensure_ascii=False)
