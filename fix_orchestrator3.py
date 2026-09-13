with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the MultiAgentOrchestrator class and replace the method definitions
idx = content.find('class MultiAgentOrchestrator:')
idx2 = content.find('\nclass ', idx + 10)
if idx2 == -1:
    idx2 = len(content)

cls_content = content[idx:idx2]

# Replace the method definitions
old_methods = '''    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        return orchestrator.get_prioritized_tasks(limit)

    def suggest_schedule(self, date: str = None) -> Dict:
        return orchestrator.suggest_schedule(date)

    def morning_briefing(self) -> str:
        return orchestrator.morning_briefing()

    def evening_review(self) -> str:
        return orchestrator.evening_review()'''

new_methods = '''    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        """Get prioritized task list using multiple factors."""
        tasks = self.task_mgr.get_tasks(status="pending")
        
        scored = []
        for t in tasks:
            score = 0
            # Urgency
            if t.get("due_date"):
                days = (t["due_date"] - time.time()) / 86400
                if days < 0:
                    score += 100
                elif days < 1:
                    score += 50
                elif days < 3:
                    score += 25
                elif days < 7:
                    score += 10
            # Priority
            score += (6 - t.get("priority", 3)) * 10
            # Progress (less progress = higher priority)
            score += (100 - t.get("progress", 0)) * 0.1
            # Energy match (prefer tasks matching current energy)
            energy = 5  # Would get from energy tracker
            if t.get("energy_level", 2) == energy:
                score += 5
            scored.append({**t, "priority_score": score})
        
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored[:limit]

    def suggest_schedule(self, date: str = None) -> Dict:
        """Suggest optimal schedule for a day."""
        if date:
            dt = datetime.strptime(date, "%Y-%m-%d")
        else:
            dt = datetime.now()
        
        tasks = self.task_mgr.get_tasks(status="pending")
        events = self.calendar_mgr.get_events(
            dt.replace(hour=0, minute=0).timestamp(),
            dt.replace(hour=23, minute=59).timestamp()
        )
        
        # Simple scheduling algorithm
        available_hours = 8
        scheduled = []
        remaining = available_hours * 60
        
        # Sort tasks by priority
        pending = [t for t in self.task_mgr.get_tasks(status="pending") if t.get("due_date")]
        pending.sort(key=lambda x: (x.get("due_date", 0), x.get("priority", 3)))
        
        for task in pending:
            if remaining <= 0:
                break
            est_min = int((task.get("estimated_hours", 1) or 1) * 60)
            if est_min <= remaining:
                scheduled.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "duration_min": est_min,
                    "priority": task["priority"]
                })
                remaining -= est_min
        
        return {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "available_hours": available_hours,
            "scheduled_tasks": scheduled,
            "buffer_minutes": remaining,
            "events": events
        }

    def morning_briefing(self) -> str:
        """Generate morning briefing text."""
        dash = self.get_dashboard()
        briefing = "Good morning! Here's your briefing for {:%A, %B %d}:\\n\\n".format(datetime.now())
        
        if dash["overdue_tasks"]:
            briefing += "⚠ {} overdue tasks need attention\\n".format(dash["overdue_tasks"])
        if dash["today_tasks"]:
            briefing += "📋 {} tasks due today\\n".format(dash["today_tasks"])
        if dash["today_events"]:
            briefing += "📅 {} events scheduled\\n".format(dash["today_events"])
        if dash["upcoming_meetings"]:
            briefing += "🤝 {} meetings in next 4 hours\\n".format(dash["upcoming_meetings"])
        if dash["inbox_count"]:
            briefing += "📥 {} items in inbox\\n".format(dash["inbox_count"])
        if dash["habits_due"]:
            briefing += "🔄 {} habits to complete\\n".format(dash["habits_due"])
        
        briefing += "\\n⚡ Energy: {} ({:.0f}/10)\\n".format(dash["energy_trend"], dash["avg_energy"])
        
        # Top priorities
        priorities = self.get_prioritized_tasks(3)
        if priorities:
            briefing += "\\n🎯 Top priorities:"
            for i, t in enumerate(priorities, 1):
                briefing += "\\n  {}. {} (due: {})".format(i, t["title"], datetime.fromtimestamp(t["due_date"]).strftime("%H:%M") if t.get("due_date") else "no due date")
        
        return briefing

    def evening_review(self) -> str:
        """Generate evening review."""
        return "Evening review - to be implemented"'''

# Find and replace the method definitions
old_methods = '''    def get_prioritized_tasks(self, limit: int = 10) -> List[Dict]:
        return orchestrator.get_prioritized_tasks(limit)

    def suggest_schedule(self, date: str = None) -> Dict:
        return orchestrator.suggest_schedule(date)

    def morning_briefing(self) -> str:
        return orchestrator.morning_briefing()

    def evening_review(self) -> str:
        return orchestrator.evening_review()'''

content = content.replace(old_methods, new_methods)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed orchestrator class methods')