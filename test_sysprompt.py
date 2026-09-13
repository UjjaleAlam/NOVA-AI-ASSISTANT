import ollama

prompt = """Output ONLY a JSON array with 3 quiz questions. Format: [{"q": "question", "a": "answer", "t": "type"}]

Topic: Python Basics
Difficulty: easy
Types: multiple_choice, true_false, short_answer"""

direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 800, 'temperature': 0.1},
    messages=[
        {'role': 'system', 'content': 'You are a JSON generator. Output ONLY valid JSON arrays. No text, no explanations, no reasoning. Only valid JSON.'},
        {'role': 'user', 'content': 'Generate 3 Python quiz questions. Format: [{"q": "question", "a": "answer", "t": "type"}]'}
    ]
)

print('Content length:', len(direct_response['message']['content']))
print('Content:', repr(direct_response['message']['content'][:800]))
print('Thinking length:', len(direct_response['message'].get('thinking', '')))