import json, urllib.request, sys

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models",
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
except Exception as e:
    print(f"FEHLER: {e}")
    sys.exit(1)

interessant = ['anthropic/claude', 'openai/gpt', 'google/gemini', 'deepseek', 'mistral']
for m in data.get('data', []):
    mid = m.get('id', '')
    if not any(i in mid for i in interessant):
        continue
    # Nur Chat-Modelle, keine Embeddings, Instruct-Preview, Image, Instruct-7b, Vision, Multimodal
    if any(x in mid for x in ['embed', 'instruct-preview', 'image', 'instruct-7b', 'vision', 'multimodal']):
        continue
    pricing = m.get('pricing', {})
    prompt = float(pricing.get('prompt', 0))
    completion = float(pricing.get('completion', 0))
    context = m.get('context_length', 0)
    print(f"{mid:<50s} Input: ${prompt:<8.4f}/M Output: ${completion:<8.4f}/M Context: {context:,} Tokens")