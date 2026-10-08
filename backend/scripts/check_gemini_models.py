"""
List the Gemini models available to GOOGLE_API_KEY (useful when updating the model seed catalog).

Usage (from the repo root):  python backend/scripts/check_gemini_models.py
"""
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not found")
    exit(1)

genai.configure(api_key=api_key)

print("=== Available Gemini Models ===\n")

try:
    models = genai.list_models()
    
    generative_models = []
    for model in models:
        # Filter for models that support generateContent
        if 'generateContent' in model.supported_generation_methods:
            generative_models.append(model)
            print(f"✓ {model.name}")
            print(f"  Display: {model.display_name}")
            print(f"  Description: {model.description}")
            print(f"  Methods: {', '.join(model.supported_generation_methods)}")
            print(f"  Input limit: {model.input_token_limit}")
            print(f"  Output limit: {model.output_token_limit}")
            print()
    
    print(f"\n=== Summary ===")
    print(f"Total generative models: {len(generative_models)}")
    
    if generative_models:
        print("\n=== Recommended Model Names for Configuration ===")
        for model in generative_models[:5]:  # Show top 5
            # Extract short model name
            model_id = model.name.replace("models/", "")
            print(f"  - {model_id}")
    
except Exception as e:
    print(f"ERROR: {e}")
