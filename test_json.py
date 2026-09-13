import ollama

prompt = 'Output ONLY a valid JSON array with 1 question: [{"question":"test","type":"short_answer","options":[],"correct_answer":"test","explanation":"test","difficulty":"easy","tags":["test"]}]'

direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 500, 'temperature': 0.1},
    messages=[{'role': 'user', 'content': prompt}]
)

print('Content length:', len(direct_response['message']['content']))
print('Content:', repr(direct_response['message']['content'][:500]))
print('Thinking length:', len(direct_response['message'].get('thinking', '')))
print('Thinking:', repr(direct_response['message'].get('thinking', '')[:300]))