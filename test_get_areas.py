import asyncio
from main import get_areas

async def test():
    res = await get_areas()
    import json
    print(json.dumps(res[:2], indent=2))

if __name__ == "__main__":
    asyncio.run(test())
