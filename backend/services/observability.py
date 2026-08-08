"""
Structured logging and observability framework for AI services.

FEATURES:
1. Structured logging with correlation IDs
2. Request/response tracing
3. Performance metrics
4. AI cost tracking
5. Quality metrics
6. Custom log formatters
"""
import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, Callable, TypeVar
from functools import wraps
from dataclasses import dataclass, field, asdict
from datetime import datetime
from contextvars import ContextVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Context variables for request tracing
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
org_id_ctx: ContextVar[Optional[int]] = ContextVar('org_id', default=None)


# =============================================================================
# REQUEST CONTEXT
# =============================================================================

@dataclass
class RequestContext:
    """Context for request tracing."""
    request_id: str
    correlation_id: str
    user_id: Optional[int] = None
    org_id: Optional[int] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat()
        }


def get_request_context() -> RequestContext:
    """Get current request context."""
    return RequestContext(
        request_id=request_id_ctx.get() or str(uuid.uuid4()),
        correlation_id=correlation_id_ctx.get() or str(uuid.uuid4()),
        user_id=user_id_ctx.get(),
        org_id=org_id_ctx.get()
    )


def set_request_context(
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None
) -> None:
    """Set request context for tracing."""
    if request_id:
        request_id_ctx.set(request_id)
    if correlation_id:
        correlation_id_ctx.set(correlation_id)
    if user_id:
        user_id_ctx.set(user_id)
    if org_id:
        org_id_ctx.set(org_id)


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, success: bool = True, error: Optional[Exception] = None) -> None:
        """Mark operation as complete."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success

        if error:
            self.error_type = type(error).__name__
            self.error_message = str(error)[:500]  # Truncate long errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "operation": self.operation,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "success": self.success,
            "error_type": self.error_type,
            "error_message": self.error_message,
            **self.metadata
        }


# =============================================================================
# AI METRICS
# =============================================================================

@dataclass
class AIMetrics:
    """Metrics specific to AI API calls."""
    model: str
    provider: str  # e.g., "openai", "anthropic"
    operation: str  # e.g., "chat_completion", "vision_analysis"

    # Token usage
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # Cost estimation (in USD)
    estimated_cost: Optional[float] = None

    # Quality metrics
    confidence_score: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # Performance
    latency_ms: Optional[float] = None
    retries: int = 0

    # Request/Response
    request_id: Optional[str] = None
    response_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}


# Pricing per 1M tokens (as of 2025)
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}


def calculate_openai_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate estimated cost for OpenAI API call.

    Args:
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Estimated cost in USD
    """
    if model not in OPENAI_PRICING:
        logger.warning(f"Unknown OpenAI model for cost calculation: {model}")
        return 0.0

    pricing = OPENAI_PRICING[model]
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


# =============================================================================
# DECORATORS
# =============================================================================

def track_performance(operation: str, **metadata):
    """
    Decorator to track performance metrics.

    Usage:
        @track_performance("screenshot_capture", url="example.com")
        def capture_screenshot(url):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            metrics = PerformanceMetrics(operation=operation, metadata=metadata)
            context = get_request_context()

            logger.info(
                f"Starting operation: {operation}",
                extra={
                    "operation": operation,
                    **context.to_dict(),
                    **metadata
                }
            )

            try:
                result = func(*args, **kwargs)
                metrics.complete(success=True)

                logger.info(
                    f"Completed operation: {operation} ({metrics.duration_ms:.2f}ms)",
                    extra={
                        **metrics.to_dict(),
                        **context.to_dict()
                    }
                )

                return result

            except Exception as e:
                metrics.complete(success=False, error=e)

                logger.error(
                    f"Failed operation: {operation} ({metrics.duration_ms:.2f}ms): {str(e)[:200]}",
                    exc_info=True,
                    extra={
                        **metrics.to_dict(),
                        **context.to_dict()
                    }
                )

                raise

        return wrapper
    return decorator


def track_ai_call(model: str, provider: str = "openai", operation: str = "completion"):
    """
    Decorator to track AI API calls with cost and quality metrics.

    Usage:
        @track_ai_call(model="gpt-4o", provider="openai", operation="vision_analysis")
        def analyze_image(image_bytes):
            response = client.chat.completions.create(...)
            return response
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            context = get_request_context()

            metrics = AIMetrics(
                model=model,
                provider=provider,
                operation=operation,
                request_id=context.request_id
            )

            logger.info(
                f"Starting AI call: {provider}/{model}/{operation}",
                extra={
                    "ai_provider": provider,
                    "ai_model": model,
                    "ai_operation": operation,
                    **context.to_dict()
                }
            )

            try:
                result = func(*args, **kwargs)

                # Extract metrics from OpenAI response
                if hasattr(result, 'usage') and result.usage:
                    metrics.prompt_tokens = result.usage.prompt_tokens
                    metrics.completion_tokens = result.usage.completion_tokens
                    metrics.total_tokens = result.usage.total_tokens

                    # Calculate cost
                    if provider == "openai":
                        metrics.estimated_cost = calculate_openai_cost(
                            model=model,
                            prompt_tokens=metrics.prompt_tokens,
                            completion_tokens=metrics.completion_tokens
                        )

                if hasattr(result, 'id'):
                    metrics.response_id = result.id

                # Calculate latency
                metrics.latency_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"Completed AI call: {provider}/{model}/{operation} "
                    f"({metrics.latency_ms:.0f}ms, {metrics.total_tokens or 0} tokens, "
                    f"${(metrics.estimated_cost or 0):.4f})",
                    extra={
                        **metrics.to_dict(),
                        **context.to_dict()
                    }
                )

                return result

            except Exception as e:
                metrics.latency_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"Failed AI call: {provider}/{model}/{operation} "
                    f"({metrics.latency_ms:.0f}ms): {str(e)[:200]}",
                    exc_info=True,
                    extra={
                        **metrics.to_dict(),
                        **context.to_dict(),
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:500]
                    }
                )

                raise

        return wrapper
    return decorator


# =============================================================================
# STRUCTURED LOGGER
# =============================================================================

class StructuredLogger:
    """
    Structured logger with automatic context injection.

    Usage:
        log = StructuredLogger("my_service")
        log.info("Processing request", extra_field="value")
    """

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.name = name

    def _build_extra(self, **kwargs) -> Dict[str, Any]:
        """Build extra dict with context."""
        context = get_request_context()
        return {
            **context.to_dict(),
            "service": self.name,
            **kwargs
        }

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, extra=self._build_extra(**kwargs))

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, extra=self._build_extra(**kwargs))

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, extra=self._build_extra(**kwargs))

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, exc_info=exc_info, extra=self._build_extra(**kwargs))

    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, exc_info=exc_info, extra=self._build_extra(**kwargs))


# =============================================================================
# JSON LOG FORMATTER
# =============================================================================

class JSONLogFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs as JSON for easy parsing by log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                               'levelname', 'levelno', 'lineno', 'module', 'msecs',
                               'message', 'pathname', 'process', 'processName',
                               'relativeCreated', 'thread', 'threadName', 'exc_info',
                               'exc_text', 'stack_info']:
                    log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def log_ai_metrics(metrics: AIMetrics) -> None:
    """
    Log AI metrics for monitoring.

    Args:
        metrics: AI metrics to log
    """
    context = get_request_context()

    logger.info(
        f"AI metrics: {metrics.provider}/{metrics.model}/{metrics.operation}",
        extra={
            **metrics.to_dict(),
            **context.to_dict()
        }
    )


def log_performance_metrics(metrics: PerformanceMetrics) -> None:
    """
    Log performance metrics for monitoring.

    Args:
        metrics: Performance metrics to log
    """
    context = get_request_context()

    logger.info(
        f"Performance metrics: {metrics.operation}",
        extra={
            **metrics.to_dict(),
            **context.to_dict()
        }
    )
