import asyncio
import httpx

import json

async def main():
    # GAP-135: Allow localhost fallback if 127.0.0.1 is not bound
    host = os.getenv("OLLAMA_HOST", "127.0.0.1")
    url = f"http://{host}:11434/v1/chat/completions"
    
    # GAP-133: Use a smaller model (1.5B) for GTX 1050 / 4GB VRAM safety
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a test."},
            {"role": "user", "content": "Respond with {'status': 'ok'} in JSON"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    try:
        print(f"Making POST request to {url} (Model: {model})")
        # GAP-134: Extended timeout for first-time model cold-start/loading
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
            print("Status:", resp.status_code)
            
            if resp.status_code == 200:
                data = resp.json()
                content = data['choices'][0]['message']['content']
                print("Raw Content:", content)
                
                # GAP-136: Robust JSON parsing to handle non-standard wrappers
                try:
                    # Clean the content in case of markdown blocks
                    clean_content = content.strip()
                    if clean_content.startswith("```json"):
                        clean_content = clean_content.split("```json")[1].split("```")[0].strip()
                    elif clean_content.startswith("```"):
                         clean_content = clean_content.split("```")[1].split("```")[0].strip()
                    
                    parsed = json.loads(clean_content)
                    print("✅ Parsed JSON:", parsed)
                    assert parsed.get("status") == "ok"
                except Exception as je:
                    print(f"❌ JSON Parsing Error: {je}")
            else:
                print(f"❌ HTTP Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print("Exception Name:", type(e).__name__)
        print("Exception:", str(e))

if __name__ == "__main__":
    import os
    asyncio.run(main())
