import requests
import pandas as pd
import json
from datetime import datetime, timezone

BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"
NOW = datetime.now(timezone.utc)

# Find a TOU plan from AGL
page = 1
found_plan = None
while not found_plan and page < 15:
    url = f"{BASE}/agl/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
    resp = requests.get(url, headers=headers_plans, timeout=10)
    plans = resp.json().get("data", {}).get("plans", [])
    for p in plans:
        if POSTCODE not in str(p.get("geography", {}).get("includedPostcodes", [])):
            continue
        # Check if currently active
        effective_to = p.get("effectiveTo")
        if effective_to:
            expiry = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
            if expiry < NOW:
                continue
        found_plan = p
        break
    page += 1

if found_plan:
    print(f"Plan: {found_plan.get('displayName')}")
    print(f"effectiveFrom: {found_plan.get('effectiveFrom')}")
    print(f"effectiveTo: {found_plan.get('effectiveTo')}")
    plan_id = found_plan.get("planId")
    detail_resp = requests.get(f"{BASE}/agl/cds-au/v1/energy/plans/{plan_id}", headers=headers_detail, timeout=10)
    detail = detail_resp.json().get("data", {})
    contract = detail.get("electricityContract", {})
    print("\n=== TARIFF PERIOD (full) ===")
    print(json.dumps(contract.get("tariffPeriod", []), indent=2))
    print("\n=== SOLAR FEED IN ===")
    print(json.dumps(contract.get("solarFeedInTariff", []), indent=2))
else:
    print("No active plan found")

pd.DataFrame(columns=["x"]).to_csv("energy-pricing.csv", index=False)
print("Done")
