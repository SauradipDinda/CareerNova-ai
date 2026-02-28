import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(timeout=45.0) as client:
        print('Testing chat for testuser99 (context verification)...')
        payload = {'message': 'What are my main skills?','history': []}
        try:
            r = await client.post('http://localhost:8000/api/chat/testuser99', json=payload)
            print(f'Status: {r.status_code}')
            data = r.json()
            print(f'Answer: {data}')
        except Exception as e:
            print(f'Test script error: {e}')

if __name__ == "__main__":
    asyncio.run(test_api())
