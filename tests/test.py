import requests
import json

def test_ollama():
    print("Testing Ollama API connection...")
    
    # 1. Check if Ollama is running by hitting the root or /api/tags
    try:
        print("\n1. Checking available models...")
        tags_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        tags_response.raise_for_status()
        models = tags_response.json().get("models", [])
        print(f"✅ Successfully connected to Ollama!")
        print(f"Found {len(models)} models.")
        for model in models:
            print(f"  - {model.get('name')}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Ollama server at http://localhost:11434")
        print(f"Error: {e}")
        print("\nMake sure the Ollama application is running!")
        return

    # 2. Test generation with 'gpt-oss-120b-cloud' (or fallback to any available model)
    target_model = "gpt-oss-120b-cloud"
    available_model_names = [m.get('name') for m in models]
    
    if target_model not in available_model_names:
        print(f"\n⚠️ Warning: Model '{target_model}' not found in available models.")
        # If there are any models, try using the first one instead just to test generation
        if available_model_names:
            target_model = available_model_names[0]
            print(f"Using '{target_model}' for generation test instead.")
        else:
            print("No models available to test generation. Please pull a model first (e.g., `ollama run llama3`).")
            return

    print(f"\n2. Testing generation endpoint (/api/generate) with model '{target_model}'...")
    payload = {
        "model": target_model,
        "prompt": "Hello! Reply with exactly one word: 'Hi'.",
        "stream": False
    }

    try:
        generate_response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        generate_response.raise_for_status()
        
        response_text = generate_response.json().get("response", "")
        print(f"✅ Generation successful!")
        print(f"Response: '{response_text.strip()}'")
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error during generation: {e}")
        print(f"Response from server: {generate_response.text}")
    except Exception as e:
        print(f"❌ Failed to generate: {e}")

if __name__ == "__main__":
    test_ollama()
