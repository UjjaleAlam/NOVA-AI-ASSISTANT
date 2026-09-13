import ollama
result = ollama.list()
print("Raw result:")
print(result)
print()
print("Models:")
for m in result.get("models", []):
    print(f"  Type: {type(m)}")
    print(f"  Content: {m}")
    if isinstance(m, dict):
        for k, v in m.items():
            print(f"    {k}: {v}")
    print()