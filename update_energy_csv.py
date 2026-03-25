import requests
import pandas as pd
import json

BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}
POSTCODE = "3929"

# Get one VIC electricity plan from AGL
page = 1
found_plan = None
while not found_plan:
    url = f"{BASE}/agl/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY&page={page}"
    resp = requests.get(url, headers=headers_plans, timeout=10)
    plans = resp.json().get("data", {}).get("plans", [])
    vic_plans = [p for p in plans if POSTCODE in str(p.get("geography", {}).get("includedPostcodes", []))]
    if vic_plans:
        found_plan = vic_plans[0]
        break
    page += 1

# Get full detail
plan_id = found_plan.get("planId")
detail_resp = requests.get(f"{BASE}/agl/cds-au/v1/energy/plans/{plan_id}", headers=headers_detail, timeout=10)
detail = detail_resp.json().get("data", {})
contract = detail.get("electricityContract", {})

print("=== PLAN NAME ===")
print(detail.get("displayName"))
print("\n=== FEES ===")
print(json.dumps(contract.get("fees", []), indent=2))
print("\n=== SOLAR FEED IN TARIFF ===")
print(json.dumps(contract.get("solarFeedInTariff", []), indent=2))
print("\n=== TARIFF PERIOD ===")
print(json.dumps(contract.get("tariffPeriod", []), indent=2))

pd.DataFrame(columns=["x"]).to_csv("energy-pricing.csv", index=False)
print("\nDone")
