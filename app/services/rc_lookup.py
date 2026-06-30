"""Vehicle RC lookup via registration number.

In DEMO mode (no RC_API_KEY set): returns realistic mock data.
In LIVE mode (RC_API_KEY set): calls the configured provider (Surepass/Eko/etc).

To go live, set two env vars on Render:
  RC_API_KEY=your_api_token
  RC_API_PROVIDER=surepass  (or "eko" or "cashfree")
"""
import os
import re
import hashlib
import httpx

RC_API_KEY = os.environ.get("RC_API_KEY", "")
RC_API_PROVIDER = os.environ.get("RC_API_PROVIDER", "surepass").lower()


def _normalize_reg(reg: str) -> str:
    return re.sub(r"[\s\-]", "", reg.strip().upper())


# ---------------------------------------------------------------------------
# MOCK DATA — deterministic per registration number so the same number
# always returns the same vehicle, making demos repeatable.
# ---------------------------------------------------------------------------

_MAKES = [
    ("HONDA", "ACTIVA 6G", "Scooter"),
    ("HONDA", "CB SHINE 125", "Motor Cycle"),
    ("BAJAJ", "PULSAR NS200", "Motor Cycle"),
    ("ROYAL ENFIELD", "CLASSIC 350", "Motor Cycle"),
    ("TVS", "JUPITER 125", "Scooter"),
    ("HERO", "SPLENDOR PLUS", "Motor Cycle"),
    ("SUZUKI", "ACCESS 125", "Scooter"),
    ("YAMAHA", "FZ-S V3", "Motor Cycle"),
    ("MARUTI SUZUKI", "SWIFT VXI", "Motor Car"),
    ("HYUNDAI", "I20 SPORTZ", "Motor Car"),
    ("TATA", "NEXON XZ PLUS", "Motor Car"),
    ("MAHINDRA", "XUV700 AX5", "Motor Car"),
    ("KIA", "SELTOS HTK PLUS", "Motor Car"),
    ("HONDA", "CITY V CVT", "Motor Car"),
    ("TOYOTA", "INNOVA CRYSTA GX", "Motor Car"),
]

_COLORS = ["WHITE", "BLACK", "SILVER", "RED", "BLUE", "GREY", "MAROON"]
_FUELS = ["PETROL", "DIESEL", "PETROL", "PETROL", "CNG", "ELECTRIC", "PETROL"]


def _mock_lookup(reg: str) -> dict:
    """Generate deterministic but realistic vehicle data from the reg number."""
    h = int(hashlib.md5(reg.encode()).hexdigest(), 16)

    make, model, vclass = _MAKES[h % len(_MAKES)]
    color = _COLORS[(h >> 8) % len(_COLORS)]
    fuel = _FUELS[(h >> 12) % len(_FUELS)]
    year = 2015 + (h % 11)  # 2015-2025
    seats = 2 if vclass in ("Motor Cycle", "Scooter") else 5

    # Parse state and RTO from reg number (e.g. MH04AB1234 → MH, 04)
    state_code = reg[:2] if len(reg) >= 2 else "MH"
    rto_code = reg[2:4] if len(reg) >= 4 else "01"

    owner_names = [
        "SANKET VERMA", "RAJESH KUMAR", "PRIYA SHARMA", "AMIT PATEL",
        "NEHA GUPTA", "VIKRAM SINGH", "ANANYA DESHMUKH", "ROHAN MEHTA",
        "SNEHA IYER", "KARAN MALHOTRA", "POOJA NAIR", "ARJUN REDDY",
    ]
    owner = owner_names[h % len(owner_names)]

    chassis = f"MA3{'ABCDEFGHJKLMNPRSTUVWXYZ'[(h>>4)%23]}{'0123456789ABCDEFGHJKLMNPRSTUVWXYZ'[(h>>6)%32]}EB1S{str(h % 10000000).zfill(7)}"
    engine = f"{'JKLMNPQRS'[(h>>3)%9]}{'0123456789'[(h>>5)%10]}{'ABCDE'[(h>>7)%5]}{str(h % 10000000).zfill(7)}"

    reg_date = f"{(h % 28) + 1:02d}/{((h >> 4) % 12) + 1:02d}/{year}"
    ins_upto = f"{(h % 28) + 1:02d}/{((h >> 4) % 12) + 1:02d}/{year + 3}"

    return {
        "success": True,
        "source": "mock",
        "data": {
            "registration_number": reg,
            "owner_name": owner,
            "father_name": f"{'RAMESH SURESH MAHESH DINESH'.split()[(h>>2)%4]} {owner.split()[-1]}",
            "maker": make,
            "model": model,
            "maker_model": f"{make} {model}",
            "vehicle_class": vclass,
            "fuel_type": fuel,
            "color": color,
            "manufacturing_year": year,
            "registration_date": reg_date,
            "seating_capacity": seats,
            "chassis_number": chassis[:17],
            "engine_number": engine[:12],
            "rto_code": f"{state_code}{rto_code}",
            "rto_name": f"RTO {state_code}-{rto_code}",
            "state": state_code,
            "insurance_company": ["ICICI LOMBARD", "HDFC ERGO", "BAJAJ ALLIANZ", "NEW INDIA ASSURANCE", "TATA AIG"][(h >> 5) % 5],
            "insurance_valid_upto": ins_upto,
            "fitness_upto": f"01/01/{year + 15}",
            "financer": ["NONE", "HDFC BANK", "ICICI BANK", "SBI", "BAJAJ FINANCE"][(h >> 6) % 5],
            "vehicle_age_years": 2026 - year,
        },
    }


# ---------------------------------------------------------------------------
# LIVE PROVIDER CALLS — add more providers by adding elif branches.
# ---------------------------------------------------------------------------

async def _surepass_lookup(reg: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://kyc-api.surepass.io/api/v1/rc/rc",
            headers={"Authorization": f"Bearer {RC_API_KEY}", "Content-Type": "application/json"},
            json={"id_number": reg},
        )
        body = resp.json()
        if not body.get("success") and not body.get("data"):
            return {"success": False, "error": body.get("message", "Lookup failed"), "source": "surepass"}
        d = body.get("data", {})
        return {
            "success": True,
            "source": "surepass",
            "data": {
                "registration_number": d.get("rc_number", reg),
                "owner_name": d.get("owner_name", ""),
                "father_name": d.get("father_name", ""),
                "maker": d.get("maker_description", ""),
                "model": d.get("maker_model", ""),
                "maker_model": d.get("maker_model", ""),
                "vehicle_class": d.get("vehicle_category_description", ""),
                "fuel_type": d.get("fuel_description", ""),
                "color": d.get("color", ""),
                "manufacturing_year": d.get("manufacturing_date_formatted", ""),
                "registration_date": d.get("registration_date", ""),
                "seating_capacity": d.get("seat_capacity", ""),
                "chassis_number": d.get("vehicle_chasi_number", ""),
                "engine_number": d.get("vehicle_engine_number", ""),
                "rto_code": d.get("registered_at", ""),
                "rto_name": d.get("registered_at", ""),
                "state": d.get("state", ""),
                "insurance_company": d.get("insurance_company", ""),
                "insurance_valid_upto": d.get("insurance_upto", ""),
                "fitness_upto": d.get("fit_up_to", ""),
                "financer": d.get("financer", ""),
                "vehicle_age_years": d.get("vehicle_age", ""),
            },
        }


async def _eko_lookup(reg: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.eko.in/ekoicici/v1/vehicles/{reg}",
            headers={"developer_key": RC_API_KEY},
        )
        body = resp.json()
        if resp.status_code != 200:
            return {"success": False, "error": body.get("message", "Lookup failed"), "source": "eko"}
        d = body.get("data", {})
        return {
            "success": True,
            "source": "eko",
            "data": {
                "registration_number": d.get("rc_number", reg),
                "owner_name": d.get("owner_name", ""),
                "father_name": d.get("father_name", ""),
                "maker": d.get("manufacturer", ""),
                "model": d.get("model", ""),
                "maker_model": f"{d.get('manufacturer', '')} {d.get('model', '')}",
                "vehicle_class": d.get("vehicle_class", ""),
                "fuel_type": d.get("fuel_type", ""),
                "color": d.get("color", ""),
                "manufacturing_year": d.get("manufacturing_year", ""),
                "registration_date": d.get("registration_date", ""),
                "seating_capacity": d.get("seating_capacity", ""),
                "chassis_number": d.get("chassis_number", ""),
                "engine_number": d.get("engine_number", ""),
                "rto_code": d.get("rto_code", ""),
                "rto_name": d.get("rto_name", ""),
                "state": d.get("state", ""),
                "insurance_company": d.get("insurance_company", ""),
                "insurance_valid_upto": d.get("insurance_upto", ""),
                "fitness_upto": d.get("fitness_upto", ""),
                "financer": d.get("financer", ""),
                "vehicle_age_years": d.get("vehicle_age", ""),
            },
        }


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

async def lookup_vehicle(reg_number: str) -> dict:
    """Look up a vehicle by registration number.

    Returns a normalized dict regardless of provider (or mock).
    """
    reg = _normalize_reg(reg_number)
    if not reg or len(reg) < 6:
        return {"success": False, "error": "Invalid registration number."}

    # DEMO mode — no API key configured
    if not RC_API_KEY:
        return _mock_lookup(reg)

    # LIVE mode
    try:
        if RC_API_PROVIDER == "eko":
            return await _eko_lookup(reg)
        else:  # default: surepass
            return await _surepass_lookup(reg)
    except Exception as e:
        return {"success": False, "error": f"Provider error: {e}"}
