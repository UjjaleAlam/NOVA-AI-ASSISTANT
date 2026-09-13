from core.offline_intelligence import list_models, generate

print('Models:')
for m in list_models():
    print(f'  {m.name} ({m.size}) quant={m.quantization} params={m.parameters}')

print()
print('Test inference:')
result = generate('Say hello in one sentence')
print(f'Success: {result["success"]}')
if result['success']:
    print(f'Response: {result["content"]}')
    print(f'TPS: {result["tokens_per_sec"]:.1f}')