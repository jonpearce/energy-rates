import requests
import pandas as pd
import json
from datetime import datetime, timezone

BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"
NOW = datetime.now(timezone.utc)

# Search through multiple retailers for an active TOU plan
found_plan = None
found_retailer = None
for retailer in ["agl", "origin", "energyaustralia", "lumo", "alinta", "globird", "momentum", "tango"]:
    if found_plan:
        break
    page = 1
    while page < 15:
        url = f"{BASE}/{retailer}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
        resp = requests.get(url, headers=headers_plans, timeout=10)
        plans = resp.json().get("data", {}).get("plans", [])
        if not plans:
            break
        for p in plans:
            if POSTCODE not in str(p.get("geography", {}).get("includedPostcodes", [])):
                continue
            effective_to = p.get("effectiveTo")
            if effective_to:
                expiry = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
                if expiry < NOW:
                    continue
            plan_id = p.get("planId")
            detail_resp = requests.get(f"{BASE}/{retailer}/cds-au/v1/energy/plans/{plan_id}", headers=headers_detail, timeout=10)
            detail = detail_resp.json().get("data", {})
            contract = detail.get("electricityContract", {})
            for period in contract.get("tariffPeriod", []):
                if period.get("timeOfUseRates"):
                    found_plan = detail
                    found_retailer = retailer
                    break
            if found_plan:
                break
        page += 1

if found_plan:
    contract = found_plan.get("electricityContract", {})
    print(f"Retailer: {found_retailer}")
    print(f"Plan: {found_plan.get('displayName')}")
    print("\n=== TARIFF PERIOD (full) ===")
    print(json.dumps(contract.get("tariffPeriod", []), indent=2))
    print("\n=== SOLAR FEED IN ===")
    print(json.dumps(contract.get("solarFeedInTariff", []), indent=2))
else:
    print("No active TOU plan found")

pd.DataFrame(columns=["x"]).to_csv("energy-pricing.csv", index=False)
print("Done")
