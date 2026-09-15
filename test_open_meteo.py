import json
import httpx
import asyncio

async def main():
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.0667,22.0257&longitude=88.0698,88.0583&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=Asia/Kolkata"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
