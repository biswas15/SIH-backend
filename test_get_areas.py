import asyncio
import sys
import json
from main import get_areas

async def run_tests():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print("Fetching /api/areas response...")
    areas = await get_areas()

    # 1. Assert exactly 30 area records are returned in the top-level list
    assert isinstance(areas, list), f"Expected list, got {type(areas)}"
    assert len(areas) == 30, f"Expected exactly 30 area records, got {len(areas)}"
    print("[PASS] Requirement 1 & 2: Top-level response returned exactly 30 area records.")

    area_map = {item["area_id"]: item for item in areas}

    # 2. Assert every record contains required keys
    required_keys = {"area_id", "area_name", "latitude", "longitude", "ward", "demographics", "current"}
    
    mapped_count = 0
    outside_count = 0

    for record in areas:
        missing_keys = required_keys - set(record.keys())
        assert not missing_keys, f"Record {record.get('area_id')} missing required keys: {missing_keys}"

        assert isinstance(record["ward"], dict), f"Record {record['area_id']} 'ward' field is not a dictionary"
        assert "ward_number" in record["ward"], f"Record {record['area_id']} 'ward' missing 'ward_number'"
        assert "mapping_status" in record["ward"], f"Record {record['area_id']} 'ward' missing 'mapping_status'"

        status = record["ward"]["mapping_status"]
        ward_num = record["ward"]["ward_number"]
        demo = record["demographics"]

        # 3. Assert mapped areas contain mapping_status == "mapped", non-null numeric ward_number, and non-null demographics
        if status == "mapped":
            mapped_count += 1
            assert ward_num is not None, f"Mapped record {record['area_id']} has ward_number None"
            assert isinstance(ward_num, (int, float)), f"Mapped record {record['area_id']} ward_number is not numeric"
            assert demo is not None, f"Mapped record {record['area_id']} has demographics None"
            assert isinstance(demo, dict), f"Mapped record {record['area_id']} demographics is not dict"
            assert "population_2011" in demo and demo["population_2011"] is not None
            assert "population_density_2011" in demo and demo["population_density_2011"] is not None
        # 4. Assert unmapped/outside areas contain mapping_status == "outside_boundary", ward_number == None, and demographics == None
        elif status == "outside_boundary":
            outside_count += 1
            assert ward_num is None, f"Outside record {record['area_id']} has ward_number {ward_num}, expected None"
            assert demo is None, f"Outside record {record['area_id']} has demographics {demo}, expected None"
        else:
            raise AssertionError(f"Record {record['area_id']} has unexpected mapping_status '{status}'")

    print(f"[PASS] Requirement 3: Every record contains required keys: {required_keys}")
    print(f"[PASS] Requirement 4: {mapped_count} mapped areas have mapping_status=='mapped', valid ward_number, and non-null demographics.")
    print(f"[PASS] Requirement 5: {outside_count} unmapped/outside areas have mapping_status=='outside_boundary', ward_number==None, and demographics==None.")

    # 5. Explicitly assert specific ward mappings
    # H04 -> Ward 1, population = 6308, density approximately 2083.05
    h04 = area_map["H04"]
    assert h04["ward"]["mapping_status"] == "mapped", f"H04 status expected 'mapped', got {h04['ward']['mapping_status']}"
    assert h04["ward"]["ward_number"] == 1, f"H04 ward_number expected 1, got {h04['ward']['ward_number']}"
    assert h04["demographics"]["population_2011"] == 6308, f"H04 population expected 6308, got {h04['demographics']['population_2011']}"
    assert abs(h04["demographics"]["population_density_2011"] - 2083.05) < 0.1, f"H04 density expected ~2083.05, got {h04['demographics']['population_density_2011']}"

    # H09 -> mapping_status == "outside_boundary"
    h09 = area_map["H09"]
    assert h09["ward"]["mapping_status"] == "outside_boundary", f"H09 status expected 'outside_boundary', got {h09['ward']['mapping_status']}"
    assert h09["ward"]["ward_number"] is None, f"H09 ward_number expected None, got {h09['ward']['ward_number']}"
    assert h09["demographics"] is None, f"H09 demographics expected None, got {h09['demographics']}"

    # H02 -> Ward 26, population = 7861
    h02 = area_map["H02"]
    assert h02["ward"]["mapping_status"] == "mapped", f"H02 status expected 'mapped', got {h02['ward']['mapping_status']}"
    assert h02["ward"]["ward_number"] == 26, f"H02 ward_number expected 26, got {h02['ward']['ward_number']}"
    assert h02["demographics"]["population_2011"] == 7861, f"H02 population expected 7861, got {h02['demographics']['population_2011']}"

    # H23 -> Ward 26
    h23 = area_map["H23"]
    assert h23["ward"]["mapping_status"] == "mapped", f"H23 status expected 'mapped', got {h23['ward']['mapping_status']}"
    assert h23["ward"]["ward_number"] == 26, f"H23 ward_number expected 26, got {h23['ward']['ward_number']}"

    # H29 -> Ward 26
    h29 = area_map["H29"]
    assert h29["ward"]["mapping_status"] == "mapped", f"H29 status expected 'mapped', got {h29['ward']['mapping_status']}"
    assert h29["ward"]["ward_number"] == 26, f"H29 ward_number expected 26, got {h29['ward']['ward_number']}"

    print("[PASS] Requirement 6: Explicit ward mappings verified:")
    print("  - H04 -> Ward 1, population=6308, density=2083.05")
    print("  - H09 -> mapping_status=='outside_boundary'")
    print("  - H02 -> Ward 26, population=7861")
    print("  - H23 -> Ward 26")
    print("  - H29 -> Ward 26")

    print("\nSUCCESS: All schema and demographic assertions passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())

