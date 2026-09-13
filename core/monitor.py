import psutil
import time
import threading
from core.logging_config import get_logger

logger = get_logger("monitor")

class SystemMonitor:
    def __init__(self, check_interval=30):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.callbacks = []
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("System monitor started")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("System monitor stopped")
        
    def register_callback(self, callback):
        self.callbacks.append(callback)
        
    def _monitor_loop(self):
        while self.running:
            try:
                self._check_system()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(self.check_interval)
            
    def _check_system(self):
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        issues = []
        
        if cpu > 90:
            issues.append(f"High CPU: {cpu}%")
        if memory.percent > 90:
            issues.append(f"High Memory: {memory.percent}%")
        if disk.percent > 95:
            issues.append(f"Low Disk: {disk.percent}%")
            
        if issues:
            msg = " | ".join(issues)
            logger.warning(f"System health: {msg}")
            for cb in self.callbacks:
                try:
                    cb(msg)
                except Exception:
                    pass
        else:
            logger.debug(f"System OK: CPU={cpu}% Mem={memory.percent}% Disk={disk.percent}%")

system_monitor = SystemMonitor()