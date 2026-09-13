from core.ai_tutor import quiz_generator, topic_manager
from brain import ask_nova
import re
import json

prompt = """Generate 3 quiz questions for: Python Basics

Topic: Variables, data types, control flow, functions
Difficulty: easy
Question types: multiple_choice, true_false, short_answer

Return as JSON array with each question having:
- question: the question text
- type: one of multiple_choice, true_false, short_answer
- options: array of strings (for multiple_choice only)
- correct_answer: the correct answer
- explanation: why this is correct
- difficulty: easy/medium/hard
- tags: relevant tags

Make questions test understanding, not just memorization."""

response = ask_nova(prompt)
print('Raw response:', repr(response))

# Check thinking field
import ollama
direct_response = ollama.chat(
    model='qwen3:8b',
    options={'num_predict': 500, 'temperature': 0.5},
    messages=[{'role': 'user', 'content': """Generate 3 quiz questions for: Python Basics

Topic: Variables, data types, control flow, functions
Difficulty: easy
Question types: multiple_choice, true_false, short_answer

Return as JSON array with each question having:
- question: the question text
- type: one of multiple_choice, true_false, short_answer
- options: array of strings (for multiple_choice only)
- correct_answer: the correct answer
- explanation: why this is correct
- difficulty: easy/medium/hard
- tags: relevant tags

Make questions test understanding, not just memorization."""}]
)

print('Direct response content:', repr(direct_response['message']['content']))
print('Direct response thinking:', repr(direct_response['message'].get('thinking', '')))