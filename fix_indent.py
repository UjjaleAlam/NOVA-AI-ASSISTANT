with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix the if __name__ block
for i, line in enumerate(lines):
    if 'if __name__ == "__main__":' in line:
        lines[i] = line + '\n    print("Multi-Agent System Agent loaded.")\n    print("Core: AgentRegistry, BaseAgent, specialized agents")\n    print("      TaskQueueManager, WorkflowEngine, MultiAgentOrchestrator")\n'
        break

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed if __name__ block')