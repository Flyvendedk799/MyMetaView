"""
Circuit Breaker Pattern for AI Services.

Prevents cascading failures by temporarily stopping requests to failing services.
Implements the classic circuit breaker state machine: CLOSED -> OPEN -> HALF_OPEN.

DESIGN:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail fast without calling service
- HALF_OPEN: Testing if service recovered, allow limited requests

FEATURES:
- Configurable failure thresholds
- Automatic recovery attempts
- Per-service isolation
- Thread-safe implementation
- Observable state changes
"""
import time
import logging
import threading
from typing import Callable, TypeVar, Optional, Dict, Any
from functools import wraps
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 2          # Successes to close from half-open
    timeout_seconds: float = 60.0       # Time before attempting recovery
    half_open_max_calls: int = 3        # Max calls allowed in half-open state

    # Error classification
    exclude_exceptions: tuple = ()      # Exceptions that don't count as failures



@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker observability."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit

    # State tracking
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    # Current window
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    half_open_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state": self.state.value,
            "state_changed_at": self.state_changed_at.isoformat() if self.state_changed_at else None,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejects calls."""
    pass


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation.

    Usage:
        cb = CircuitBreaker(name="openai", config=CircuitBreakerConfig())

        @cb.protect
        def call_openai():
            return client.chat.completions.create(...)
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            name: Unique identifier for this circuit breaker
            config: Configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()
        self._state_changed_at = time.time()

        logger.info(
            f"Circuit breaker initialized: {name}",
            extra={
                "circuit_breaker": name,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                }
            }
        )

    def _transition_to(self, new_state: CircuitState) -> None:
        """Thread-safe state transition."""
        with self._lock:
            old_state = self.metrics.state
            if old_state != new_state:
                self.metrics.state = new_state
                self.metrics.state_changed_at = datetime.utcnow()
                self._state_changed_at = time.time()

                # Reset counters on state change
                if new_state == CircuitState.HALF_OPEN:
                    self.metrics.half_open_calls = 0
                    self.metrics.consecutive_successes = 0

                logger.warning(
                    f"Circuit breaker state transition: {self.name} {old_state.value} -> {new_state.value}",
                    extra={
                        "circuit_breaker": self.name,
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "metrics": self.metrics.to_dict()
                    }
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        with self._lock:
            if self.metrics.state != CircuitState.OPEN:
                return False

            time_since_open = time.time() - self._state_changed_at
            return time_since_open >= self.config.timeout_seconds

    def _before_call(self) -> None:
        """Check circuit state before allowing call."""
        with self._lock:
            self.metrics.total_calls += 1

            if self.metrics.state == CircuitState.CLOSED:
                # Normal operation
                return

            elif self.metrics.state == CircuitState.OPEN:
                # Check if we should attempt recovery
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
                    return

                # Still open, reject call
                self.metrics.rejected_calls += 1
                logger.warning(
                    f"Circuit breaker rejecting call: {self.name} (state=OPEN)",
                    extra={
                        "circuit_breaker": self.name,
                        "state": "open",
                        "rejected_calls": self.metrics.rejected_calls
                    }
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. Service temporarily unavailable."
                )

            elif self.metrics.state == CircuitState.HALF_OPEN:
                # Limit concurrent calls in half-open state
                if self.metrics.half_open_calls >= self.config.half_open_max_calls:
                    self.metrics.rejected_calls += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN with max concurrent calls reached."
                    )

                self.metrics.half_open_calls += 1

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            self.metrics.successful_calls += 1
            self.metrics.last_success_time = datetime.utcnow()
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes += 1

            if self.metrics.state == CircuitState.HALF_OPEN:
                # Check if we've had enough successes to close circuit
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    logger.info(
                        f"Circuit breaker recovered: {self.name}",
                        extra={
                            "circuit_breaker": self.name,
                            "consecutive_successes": self.metrics.consecutive_successes
                        }
                    )
                    self._transition_to(CircuitState.CLOSED)
                    self.metrics.consecutive_successes = 0

    def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        with self._lock:
            # Check if this exception should be excluded
            if isinstance(exception, self.config.exclude_exceptions):
                logger.debug(
                    f"Circuit breaker ignoring excluded exception: {self.name}",
                    extra={
                        "circuit_breaker": self.name,
                        "exception_type": type(exception).__name__
                    }
                )
                return

            self.metrics.failed_calls += 1
            self.metrics.last_failure_time = datetime.utcnow()
            self.metrics.consecutive_successes = 0
            self.metrics.consecutive_failures += 1

            if self.metrics.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately reopens circuit
                logger.warning(
                    f"Circuit breaker reopening after failure in HALF_OPEN: {self.name}",
                    extra={
                        "circuit_breaker": self.name,
                        "exception": str(exception)
                    }
                )
                self._transition_to(CircuitState.OPEN)
                self.metrics.consecutive_failures = 0

            elif self.metrics.state == CircuitState.CLOSED:
                # Check if we've exceeded failure threshold
                if self.metrics.consecutive_failures >= self.config.failure_threshold:
                    logger.error(
                        f"Circuit breaker opening due to failures: {self.name}",
                        extra={
                            "circuit_breaker": self.name,
                            "consecutive_failures": self.metrics.consecutive_failures,
                            "threshold": self.config.failure_threshold
                        }
                    )
                    self._transition_to(CircuitState.OPEN)
                    self.metrics.consecutive_failures = 0

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        self._before_call()

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to protect a function with circuit breaker.

        Usage:
            @circuit_breaker.protect
            def my_function():
                pass
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)

        return wrapper

    def record_success(self) -> None:
        """Report a successful call the breaker did not itself make.

        ``call()`` wraps a callable, which does not fit work that races two
        providers or spans a thread pool. Those paths report their outcome here
        instead of reaching into the private handlers.
        """
        self._on_success()

    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Report a failed call the breaker did not itself make."""
        self._on_failure(exception or Exception("unspecified failure"))

    # Older callers (pipeline_context, preview_reasoning) use this spelling.
    record_error = record_failure

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        with self._lock:
            return self.metrics.to_dict()

    def get_state(self) -> CircuitState:
        """Get current state."""
        with self._lock:
            return self.metrics.state

    def is_open(self) -> bool:
        """Should callers skip the protected work right now?

        HALF_OPEN counts as closed: the whole point of that state is to let one
        probe through, and reporting it as open would mean the breaker never
        gets the success it needs to recover.
        """
        with self._lock:
            if self.metrics.state != CircuitState.OPEN:
                return False
        return not self._should_attempt_reset()

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            logger.info(f"Manually resetting circuit breaker: {self.name}")
            self._transition_to(CircuitState.CLOSED)
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes = 0


# =============================================================================
# GLOBAL CIRCUIT BREAKER REGISTRY
# =============================================================================

class CircuitBreakerRegistry:
    """Global registry for circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        with self._lock:
            return self._breakers.get(name)

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


# Global registry instance
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker.

    Args:
        name: Unique identifier for the circuit breaker
        config: Configuration (optional)

    Returns:
        CircuitBreaker instance
    """
    return _registry.get_or_create(name, config)


def get_all_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all circuit breakers."""
    return _registry.get_all_metrics()
