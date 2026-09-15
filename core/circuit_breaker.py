"""
Circuit Breaker Pattern Implementation
Provides fault tolerance for unreliable external dependencies.
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from functools import wraps


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation, requests go through
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5        # Failures before opening
    success_threshold: int = 2        # Successes in half-open to close
    timeout: float = 30.0             # Seconds before trying half-open
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


@dataclass
class CircuitBreakerState:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState()
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if not self._can_execute():
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise
    
    def _can_execute(self) -> bool:
        """Check if request can proceed based on circuit state."""
        if self.state.state == CircuitState.CLOSED:
            return True
        
        if self.state.state == CircuitState.OPEN:
            # Check if timeout has passed to transition to half-open
            if time.time() - self.state.last_failure_time >= self.config.timeout:
                self._transition_to_half_open()
                return True
            return False
        
        # HALF_OPEN - allow one request through
        return True
    
    def _on_success(self):
        """Handle successful execution."""
        with self._lock:
            if self.state.state == CircuitState.HALF_OPEN:
                self.state.success_count += 1
                if self.state.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.state.failure_count = 0
    
    def _on_failure(self):
        """Handle failed execution."""
        with self._lock:
            self.state.failure_count += 1
            self.state.last_failure_time = time.time()
            
            if self.state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to_open()
            elif self.state.state == CircuitState.CLOSED:
                if self.state.failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state.state = CircuitState.OPEN
        self.state.success_count = 0
        self.state.last_state_change = time.time()
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state.state = CircuitState.HALF_OPEN
        self.state.success_count = 0
        self.state.last_state_change = time.time()
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state.state = CircuitState.CLOSED
        self.state.failure_count = 0
        self.state.success_count = 0
        self.state.last_state_change = time.time()
    
    def get_state(self) -> Dict:
        """Get current circuit breaker status."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.state.value,
                "failure_count": self.state.failure_count,
                "success_count": self.state.success_count,
                "last_failure_time": self.state.last_failure_time,
                "last_state_change": self.state.last_state_change
            }
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._transition_to_closed()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""
    pass


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_circuit_breaker_lock = threading.Lock()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    with _circuit_breaker_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, config)
        return _circuit_breakers[name]


def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator to add circuit breaker protection to a function."""
    def decorator(func: Callable):
        cb = get_circuit_breaker(name, config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Pre-configured circuit breakers for common dependencies
def get_ollama_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Ollama LLM calls."""
    return get_circuit_breaker("ollama", CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=60.0,
        expected_exception=(Exception,)
    ))


def get_blender_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Blender operations."""
    return get_circuit_breaker("blender", CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=120.0,  # Longer timeout for rendering
        expected_exception=(Exception,)
    ))


def get_database_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for database operations."""
    return get_circuit_breaker("database", CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        timeout=30.0,
        expected_exception=(Exception,)
    ))


# Convenience functions for common patterns
def with_ollama_circuit_breaker(func: Callable):
    """Decorator to add Ollama circuit breaker to a function."""
    cb = get_ollama_circuit_breaker()
    @wraps(func)
    def wrapper(*args, **kwargs):
        return cb.call(func, *args, **kwargs)
    return wrapper


def with_blender_circuit_breaker(func: Callable):
    """Decorator to add Blender circuit breaker to a function."""
    cb = get_blender_circuit_breaker()
    @wraps(func)
    def wrapper(*args, **kwargs):
        return cb.call(func, *args, **kwargs)
    return wrapper


def with_database_circuit_breaker(func: Callable):
    """Decorator to add database circuit breaker to a function."""
    cb = get_database_circuit_breaker()
    @wraps(func)
    def wrapper(*args, **kwargs):
        return cb.call(func, *args, **kwargs)
    return wrapper


# Health check integration
def get_all_circuit_breaker_states() -> Dict[str, Dict]:
    """Get status of all circuit breakers."""
    with _circuit_breaker_lock:
        return {name: cb.get_state() for name, cb in _circuit_breakers.items()}


if __name__ == "__main__":
    # Demo
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, timeout=5.0))
    
    @circuit_breaker("demo", CircuitBreakerConfig(failure_threshold=2, timeout=2.0))
    def unreliable_function(should_fail: bool):
        if should_fail:
            raise Exception("Simulated failure")
        return "success"
    
    print("Testing circuit breaker...")
    for i in range(5):
        try:
            result = unreliable_function(i >= 2)  # Fail on 3rd and 4th calls
            print(f"Call {i+1}: {result}")
        except Exception as e:
            print(f"Call {i+1}: {type(e).__name__}: {e}")
        
        print(f"Circuit state: {get_circuit_breaker('demo').get_state()['state']}")
        
        time.sleep(3)  # Wait for timeout
        
        try:
            result = unreliable_function(False)
            print(f"After recovery: {result}")
        except Exception as e:
            print(f"After recovery: {e}")
        
        print(f"Final state: {get_circuit_breaker('demo').get_state()['state']}")