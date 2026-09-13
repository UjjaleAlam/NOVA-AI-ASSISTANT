with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''if __name__ == "__main__":
    print("Multi-Agent System Agent loaded.")
    print("Core: AgentRegistry, BaseAgent, specialized agents")
    print("      TaskQueueManager, WorkflowEngine, MultiAgentOrchestrator")'''

new = '''def get_prioritized_tasks(limit: int = 10) -> List[Dict]:
    return orchestrator.get_prioritized_tasks(limit)


def suggest_schedule(date: str = None) -> Dict:
    return orchestrator.suggest_schedule(date)


def morning_briefing() -> str:
    return orchestrator.morning_briefing()


def evening_review() -> str:
    return orchestrator.evening_review()


def capture_quick(content: str, **kwargs) -> str:
    return quick_capture.capture(content, **kwargs)


if __name__ == "__main__":'''

content = content.replace(
    '''if __name__ == "__main__":
    print("Multi-Agent System Agent loaded.")
    print("Core: AgentRegistry, BaseAgent, specialized agents")
    print("      TaskQueueManager, WorkflowEngine, MultiAgentOrchestrator")''',
    new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Added module-level wrapper functions')