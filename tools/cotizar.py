"""
Tool: cotizar_planes
Cotiza planes ACA reales usando la API de Healthcare.gov Marketplace.
Calcula subsidio APTC, CSR, y las 3 opciones de planes (Básico, Medium, Full Cover)
incluyendo los add-ons de protección suplementaria.

Basado en cotizador_fix.py (Sara v1) — adaptado a tool schema de Anthropic.
"""

import json
import os
import traceback
import httpx

# ============================================================
# CONFIGURACIÓN
# ============================================================

HEALTHCARE_API_KEY = os.getenv("HEALTHCARE_API_KEY", "XIvzGUQ5RSDAAqGFukLxcmrJ8P2zcCik")
BASE_URL = "https://marketplace.api.healthcare.gov/api/v1"

COMPANIAS_PREFERIDAS = ["oscar", "ambetter", "florida blue", "unitedhealthcare", "united"]
NIVELES_OK = ["silver", "gold"]

# Precios fijos de protección suplementaria (Washington National)
WN_ACCIDENTE = 38.50
WN_HOSP_BAJA = 45.00   # cuando deducible == 0
WN_HOSP_ALTA = 65.00   # cuando deducible > 0

# ============================================================
# SCHEMA
# ============================================================

TOOL_SCHEMA = {
    "name": "cotizar_planes",
    "description": (
        "Cotiza planes de seguro de salud reales usando la API de Healthcare.gov. "
        "Calcula el subsidio real (APTC) según ingresos y devuelve 3 opciones: "
        "Básico, Medium y Full Cover con sus precios. "
        "Usar SOLO cuando se tengan: ZIP verificado, ingreso anual, y edades de todos los miembros."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "zip_code": {
                "type": "string",
                "description": "Código ZIP de 5 dígitos verificado"
            },
            "ingreso_anual": {
                "type": "number",
                "description": "Ingreso anual del hogar en dólares"
            },
            "edades": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Lista de edades de todas las personas a cubrir. Ej: [35, 32, 5]"
            },
            "tipo_ingreso": {
                "type": "string",
                "enum": ["w2", "1099", "cash"],
                "description": "Tipo de ingreso: w2 (empleado), 1099 o cash (independiente)"
            },
            "filing": {
                "type": "string",
                "enum": ["individual", "pareja"],
                "description": "Si declara taxes solo o con pareja"
            }
        },
        "required": ["zip_code", "ingreso_anual", "edades"]
    }
}

# ============================================================
# FPL Y CONTRIBUCIÓN
# ============================================================

FPL_2025 = {
    1: 15060, 2: 20440, 3: 25820, 4: 31200,
    5: 36580, 6: 41960, 7: 47340, 8: 52720
}

CONTRIBUTION_TABLE = [
    (0,   150,  0.0),
    (150, 200,  0.0),
    (200, 250,  2.0),
    (250, 300,  4.0),
    (300, 400,  6.0),
    (400, 9999, 8.5),
]


def _calcular_fpl(ingreso: float, num_personas: int) -> tuple:
    fpl = FPL_2025.get(num_personas, FPL_2025[8] + (num_personas - 8) * 4480)
    pct_fpl = (ingreso / fpl) * 100
    contrib_pct = 8.5
    for mn, mx, pct in CONTRIBUTION_TABLE:
        if mn <= pct_fpl < mx:
            contrib_pct = pct
            break
    contrib_mensual = (ingreso * contrib_pct / 100) / 12
    csr = None
    if pct_fpl < 150:
        csr = "CSR94"
    elif pct_fpl < 200:
        csr = "CSR87"
    elif pct_fpl < 250:
        csr = "CSR73"
    return contrib_mensual, csr, round(pct_fpl, 1)


# ============================================================
# API HEALTHCARE.GOV
# ============================================================

def _get_fips(zipcode: str) -> tuple:
    try:
        r = httpx.get(
            f"{BASE_URL}/counties/by/zip/{zipcode}",
            params={"apikey": HEALTHCARE_API_KEY},
            timeout=10
        )
        if r.status_code == 200:
            counties = r.json().get("counties", [])
            if counties:
                return counties[0].get("fips", ""), counties[0].get("state", "FL")
    except Exception as e:
        print(f"[FIPS] Error: {e}")
    return "", "FL"


def _get_benchmark(zipcode: str, fips: str, state: str, personas: list) -> float:
    try:
        people = [{"age": max(1, p), "uses_tobacco": False, "aptc_eligible": True} for p in personas]
        payload = {
            "aptc_override": 0,
            "household": {"income": 999999, "people": people},
            "market": "Individual",
            "place": {"countyfips": fips, "state": state, "zipcode": zipcode},
            "year": 2025,
            "filter": {"metal_levels": ["Silver"]}
        }
        r = httpx.post(
            f"{BASE_URL}/plans/search",
            params={"apikey": HEALTHCARE_API_KEY},
            json=payload,
            timeout=20
        )
        if r.status_code == 200:
            planes = sorted(
                [p for p in r.json().get("plans", []) if p.get("metal_level", "").lower() == "silver"],
                key=lambda x: float(x.get("premium", 9999) or 9999)
            )
            if len(planes) >= 2:
                return float(planes[1].get("premium", 0))
            elif len(planes) == 1:
                return float(planes[0].get("premium", 0))
    except Exception as e:
        print(f"[BENCHMARK] Error: {e}")
    return 0.0


def _buscar_planes(zipcode: str, fips: str, state: str, ingreso: float,
                   personas: list, contrib: float, csr: str) -> tuple:
    try:
        people = [{"age": max(1, p), "uses_tobacco": False, "aptc_eligible": True} for p in personas]
        benchmark = _get_benchmark(zipcode, fips, state, personas)

        if benchmark > 0:
            aptc = max(0.0, benchmark - contrib)
        else:
            aptc = 0.0

        payload = {
            "aptc_override": round(aptc, 2),
            "household": {"income": ingreso, "people": people},
            "market": "Individual",
            "place": {"countyfips": fips, "state": state, "zipcode": zipcode},
            "year": 2025,
            "filter": {"metal_levels": ["Silver", "Gold"]}
        }
        if csr:
            payload["csr_override"] = csr

        r = httpx.post(
            f"{BASE_URL}/plans/search",
            params={"apikey": HEALTHCARE_API_KEY},
            json=payload,
            timeout=20
        )
        if r.status_code == 200:
            return r.json().get("plans", []), aptc
    except Exception as e:
        print(f"[PLANES] Error: {e}")
        traceback.print_exc()
    return [], 0.0


def _filtrar_rankear(planes_raw: list, aptc: float) -> tuple:
    preferidas = []
    otras = []

    for plan in planes_raw:
        issuer = plan.get("issuer", {}).get("name", "").lower()
        nivel = plan.get("metal_level", "").lower()
        if nivel not in NIVELES_OK:
            continue

        precio_bruto = float(plan.get("premium", 0) or 0)
        precio_subsidio = float(plan.get("premium_w_credit") or max(0, precio_bruto - aptc))
        precio_subsidio = max(0.0, precio_subsidio)

        deds = plan.get("deductibles", [])
        ded = float(deds[0].get("amount", 0) or 0) if deds else 0.0

        moops = plan.get("moops", [])
        moop = float(moops[0].get("amount", 0) or 0) if moops else 0.0

        es_preferida = any(c in issuer for c in COMPANIAS_PREFERIDAS)

        entry = {
            "nombre": plan.get("name", "")[:60],
            "issuer": plan.get("issuer", {}).get("name", ""),
            "nivel": plan.get("metal_level", ""),
            "precio_bruto": round(precio_bruto, 2),
            "precio_con_subsidio": round(precio_subsidio, 2),
            "deducible": ded,
            "moop": moop,
            "es_preferida": es_preferida,
            "plan_id": plan.get("id", "")
        }

        if es_preferida:
            preferidas.append(entry)
        else:
            otras.append(entry)

    preferidas.sort(key=lambda x: x["precio_con_subsidio"])
    otras.sort(key=lambda x: x["precio_con_subsidio"])
    return preferidas, otras


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def ejecutar(zip_code: str, ingreso_anual: float, edades: list,
             tipo_ingreso: str = "w2", filing: str = "individual") -> str:
    try:
        personas = [int(e) for e in edades if e is not None]
        if not personas:
            return json.dumps({"exito": False, "error": "Se necesitan las edades de las personas a cubrir"})

        fips, state = _get_fips(zip_code)
        if not fips:
            return json.dumps({"exito": False, "error": f"No se pudo obtener información del ZIP {zip_code}"})

        contrib, csr, pct_fpl = _calcular_fpl(float(ingreso_anual), len(personas))
        planes_raw, aptc = _buscar_planes(zip_code, fips, state, float(ingreso_anual),
                                          personas, contrib, csr)

        if not planes_raw:
            return json.dumps({
                "exito": False,
                "sin_planes": True,
                "mensaje": "No se encontraron planes en esta zona. El asesor puede ayudar directamente."
            })

        preferidas, otras = _filtrar_rankear(planes_raw, aptc)
        top3 = preferidas[:3]
        if len(top3) < 3:
            top3 += otras[:3 - len(top3)]

        if not top3:
            return json.dumps({
                "exito": False,
                "sin_planes": True,
                "mensaje": "No se encontraron planes elegibles. El asesor puede ayudar directamente."
            })

        # Tomar el mejor plan para calcular las 3 opciones con WN
        mejor = top3[0]
        precio_aca = mejor["precio_con_subsidio"]
        deducible = mejor["deducible"]

        hosp = WN_HOSP_BAJA if deducible == 0 else WN_HOSP_ALTA

        opciones = {
            "basico": round(precio_aca, 2),
            "medium": round(precio_aca + WN_ACCIDENTE, 2),
            "full": round(precio_aca + hosp + WN_ACCIDENTE, 2)
        }

        issuer = mejor.get("issuer", "")
        if isinstance(issuer, dict):
            issuer = issuer.get("name", "")

        return json.dumps({
            "exito": True,
            "zip": zip_code,
            "estado": state,
            "fpl_porcentaje": pct_fpl,
            "aptc_mensual": round(aptc, 2),
            "csr": csr,
            "tipo_ingreso": tipo_ingreso,
            "mejor_plan": {
                "nombre": mejor["nombre"],
                "issuer": issuer,
                "nivel": mejor["nivel"],
                "precio_bruto": mejor["precio_bruto"],
                "precio_con_subsidio": precio_aca,
                "deducible": int(deducible),
                "moop": int(mejor["moop"])
            },
            "opciones_para_asesor": {
                "basico_mensual": opciones["basico"],
                "medium_mensual": opciones["medium"],
                "full_mensual": opciones["full"]
            },
            "total_planes_encontrados": len(planes_raw),
            "planes_preferidas": len(preferidas),
            "nota_interna": (
                "Cotización procesada. Sara NO debe mencionar precios. "
                "Continuar con siembra del dolor y presentar los 3 planes con beneficios."
            )
        }, ensure_ascii=False)

    except Exception as e:
        traceback.print_exc()
        return json.dumps({
            "exito": False,
            "error": f"Error al cotizar: {str(e)}",
            "mensaje": "No pudimos obtener precios ahora. El asesor puede ayudar directamente."
        }, ensure_ascii=False)
