"""
List the Groq models available to GROQ_API_KEY (useful when updating the model seed catalog).

Usage (from the repo root):  python backend/scripts/list_groq_models.py
"""
import asyncio
from groq import AsyncGroq
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")


async def list_models():
    """List all available Groq models."""
    try:
        import httpx
        client = AsyncGroq(api_key=api_key, http_client=httpx.AsyncClient())
        
        models = await client.models.list()
        
        print("=== Available Groq Models ===\n")
        for model in models.data:
            print(f"✓ {model.id}")
            if hasattr(model, 'owned_by'):
                print(f"  Owner: {model.owned_by}")
            if hasattr(model, 'context_window'):
                print(f"  Context: {model.context_window}")
            print()
        
        await client.close()
        return [m.id for m in models.data]
        
    except Exception as e:
        print(f"Error listing models: {e}")
        return []


if __name__ == "__main__":
    models = asyncio.run(list_models())
    if models:
        print(f"\n=== Total: {len(models)} models ===")
        print("\nRecommended for planning:")
        for m in models:
            if any(x in m.lower() for x in ['70b', 'large', 'mixtral-8x7b', 'llama3-70b']):
                print(f"  - {m}")
