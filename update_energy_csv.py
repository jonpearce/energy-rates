import requests
import pandas as pd

POSTCODE = "3929"
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
    if not tp:
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
        print(f"Trying {r}: {url}")
        resp = requests.get(url, headers=headers_plans, timeout=10)
        print(f"{r} status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Failed plans for {r}: {resp.status_code} {resp.text[:200]}")
            continue
        data = resp.json()
        plans = data.get("data", {}).get("plans", [])
        print(f"{r} plans found: {len(plans)}")
        for plan in plans:
            try:
                if plan.get("fuelType") != "ELECTRICITY":
                    continue
                if "VIC" not in str(plan.get("geography", {})):
                    continue
                plan_id = plan.get("planId")
                if not plan_id:
                    continue
                detail_url = f"{BASE}/{r}/cds-au/v1/energy/plans/{plan_id}"
                detail_resp = requests.get(detail_url, headers=headers_detail, timeout=10)
                if detail_resp.status_code != 200:
                    continue
                detail = detail_resp.json()
                charges = detail.get("electricityCharges", {})
                rows.append({
                    "Heading": plan.get("displayName", "Unknown"),
                    "Import": "",
                    "Export": ""
                })
                tariffs = charges.get("tariffRates", [])
                if not tariffs:
                    continue
                for t in tariffs:
                    rows.append({
                        "Heading": map_time_period(t.get("timePeriod")),
                        "Import": t.get("rate", ""),
                        "Export": t.get("feedInTariff", "")
                    })
            except Exception as e:
                print(f"Plan error: {e}")
    except Exception as e:
        print(f"Retailer error: {r} {e}")

print(f"Total rows collected: {len(rows)}")
df = pd.DataFrame(rows)
if not df.empty:
    df.to_csv("energy-pricing.csv", index=False)
    print(f"Saved {len(df)} rows to energy-pricing.csv")
else:
    print("No data collected - creating empty placeholder")
    pd.DataFrame(columns=["Heading", "Import", "Export"]).to_csv("energy-pricing.csv", index=False)
