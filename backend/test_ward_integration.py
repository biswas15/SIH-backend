import json, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")

for aid in ["H01", "H09", "H17"]:
    try:
        url = f"http://127.0.0.1:8000/api/weather?area_id={aid}"
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        print(f"--- {aid} ---")
        print(f"  ward_number:         {data.get('ward_number')}")
        print(f"  ward_mapping_status: {data.get('ward_mapping_status')}")
        demo = data.get("ward_demographics")
        if demo:
            print(f"  population_2011:     {demo.get('population_2011')}")
            print(f"  population_density:  {demo.get('population_density_2011')}")
            print(f"  area_km2:            {demo.get('area_km2')}")
        else:
            print(f"  ward_demographics:   None")
        print(f"  weather temp:        {data['current']['temperature']}")
    except Exception as e:
        print(f"  ERROR {aid}: {e}")
