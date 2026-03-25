import requests
import pandas as pd

RETAILERS = ["agl"]
BASE = "https://cdr.energymadeeasy.gov.au"
headers_plans = {"x-v": "1", "x-min-v": "1"}
headers_detail = {"x-v": "3"}

for r in RETAILERS:
    try:
        url = f"{BASE}/{r}/cds-au/v1/energy/plans?page-size=100&fuelType=ELECTRICITY"
        resp = requests.get(url, headers=headers_plans, timeout=10)
        data = resp.json()
        plans = data.get("data", {}).get("plans", [])
        print(f"Plans found: {len(plans)}")
        if plans:
            # Print geography of first plan to see structure
            print(f"First plan geography: {plans[0].get('geography', {})}")
            # Check what postcodes appear across all plans
            all_postcodes = set()
            for p in plans:
                postcodes = p.get("geography", {}).get("includedPostcodes", [])
                all_postcodes.update(postcodes)
            vic_postcodes = [pc for pc in all_postcodes if pc.startswith("3")]
            print(f"VIC postcodes found: {sorted(vic_postcodes)[:50]}")
    except Exception as e:
        print(f"Error: {e}")

pd.DataFrame(columns=["Heading","Import","Export"]).to_csv("energy-pricing.csv", index=False)
print("Done")
