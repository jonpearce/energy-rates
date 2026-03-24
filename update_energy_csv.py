import requests
import pandas as pd

POSTCODE = "3936"  # change if needed

RETAILERS = [
    "agl", "origin", "energyaustralia", "redenergy",
    "lumo", "alinta", "powershop", "dodo",
    "tango", "globird", "sumo", "momentum"
]

BASE = "https://cdr.energymadeeasy.gov.au"

headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}

rows = []

def map_time_period(tp):
    if tp is None:
        return "0-24"

    tp = tp.upper()

    if "OFF" in tp:
        return "0-6"
    if "PEAK" in tp:
        return "6-24"

    return "0-24"


for r in RETAILERS:
    try:
        url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=1000"
        resp = requests.get(url, headers=headers_plans).json()

        for plan in resp.get("data", {}).get("plans", []):
            if plan.get("fuelType") != "ELECTRICITY":
                continue

            if "VIC" not in str(plan.get("geography", {})):
                continue

            plan_id = plan["planId"]

            detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
            detail = requests.get(detail_url, headers=headers_detail).json()

            charges = detail.get("electricityCharges", {})

            # ---- HEADER ROW (like your file)
            rows.append({
                "Heading": plan.get("displayName"),
                "Import": "",
                "Export": ""
            })

            tariffs = charges.get("tariffRates", [])

            if not tariffs:
                continue

            for t in tariffs:
                rows.append({
                    "Heading": map_time_period(t.get("timePeriod")),
                    "Import": t.get("rate"),
                    "Export": t.get("feedInTariff", "")
                })

    except Exception as e:
        print(f"Error with {r}: {e}")

df = pd.DataFrame(rows)

df.to_csv("energy-pricing.csv", index=False)
