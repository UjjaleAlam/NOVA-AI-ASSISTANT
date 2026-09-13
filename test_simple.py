import ollama

prompt = """Output ONLY a valid JSON array. No text before or after.

[
  {"question": "What is 2+2?", "type": "short_answer", "options": [], "correct_answer": "4", "explanation": "2+2=4", "difficulty": "easy", "tags": ["math"]}
]"""

direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 200, 'temperature': 0.1},
    messages=[{'role': 'user', 'content': prompt}]
)

print('Content:', repr(direct_response['message']['content']))
print('Thinking:', repr(direct_response['message'].get('thinking', '')[:200]))