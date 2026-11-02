import json

log_path = r"C:\Users\sebas\.gemini\antigravity\brain\82707afb-c487-4edb-8c5e-f1ea1cf5befd\.system_generated\logs\transcript.jsonl"
keywords = ["Leipzig", "Dark", "18"]

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get("type") == "USER_INPUT":
                    content = data.get("content", "")
                    if any(k.lower() in content.lower() for k in keywords):
                        print(f"--- MSG {i} ---")
                        print(content[:500] + "..." if len(content)>500 else content)
            except:
                pass
except Exception as e:
    print("Error:", e)
