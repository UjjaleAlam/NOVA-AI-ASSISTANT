import ollama

prompt = """Output ONLY a valid JSON array with 3 quiz questions. No explanations, no reasoning, just the JSON array.

Format:
[
  {
    "question": "question text",
    "type": "one of multiple_choice, true_false, short_answer",
    "options": ["opt1", "opt2", "opt3", "opt4"],
    "correct_answer": "answer",
    "explanation": "why correct",
    "difficulty": "easy/medium/hard",
    "tags": ["tag1", "tag2"]
  }
]

Topic: Variables, data types, control flow, functions
Difficulty: easy
Question types: multiple_choice, true_false, short_answer

Make questions test understanding of: Python Basics"""

direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 1200, 'temperature': 0.1},
    messages=[{'role': 'user', 'content': prompt}]
)

print('Content length:', len(direct_response['message']['content']))
print('Content:', repr(direct_response['message']['content'][:500]))
print('Thinking length:', len(direct_response['message'].get('thinking', '')))
print('Thinking:', repr(direct_response['message'].get('thinking', '')[:500]))