import ollama

prompt = 'Generate 3 Python quiz questions. Output ONLY a JSON array with format: [{"q": "question", "a": "answer", "t": "type"}]'

direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 800, 'temperature': 0.1},
    messages=[
        {'role': 'system', 'content': 'You are a JSON generator. Output ONLY valid JSON arrays. No text, no explanations, no reasoning. Only valid JSON.'},
        {'role': 'user', 'content': prompt}
    ]
)

print('Content length:', len(direct_response['message']['content']))
print('Content:', repr(direct_response['message']['content'][:800]))
print('Thinking length:', len(direct_response['message'].get('thinking', '')))