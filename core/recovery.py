import time
import subprocess
import threading
from core.logging_config import get_logger
from core.signal_bus import signal_bus

logger = get_logger("recovery")

class RecoveryManager:
    def __init__(self):
        self.restart_counts = {}
        self.max_restarts = 3
        self.restart_window = 300
        
    def register_failure(self, component):
        now = time.time()
        if component not in self.restart_counts:
            self.restart_counts[component] = []
        self.restart_counts[component].append(now)
        self.restart_counts[component] = [
            t for t in self.restart_counts[component] 
            if now - t < self.restart_window
        ]
        
    def can_restart(self, component):
        return len(self.restart_counts.get(component, [])) < self.max_restarts
        
    def restart_component(self, component, restart_func):
        if not self.can_restart(component):
            logger.error(f"Max restarts exceeded for {component}")
            signal_bus.speak.emit(f"Cannot recover {component}, max retries reached")
            return False
            
        self.register_failure(component)
        logger.warning(f"Restarting {component} (attempt {len(self.restart_counts[component])}/{self.max_restarts})")
        
        def delayed_restart():
            time.sleep(2)
            try:
                restart_func()
                logger.info(f"{component} restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart {component}: {e}")
                
        threading.Thread(target=delayed_restart, daemon=True).start()
        return True
        
    def reset(self, component):
        if component in self.restart_counts:
            del self.restart_counts[component]

recovery_manager = RecoveryManager()