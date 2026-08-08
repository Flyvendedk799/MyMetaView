"""
AI Provider Abstraction Layer.

Provides a unified interface for interacting with multiple AI providers
(OpenAI, Anthropic, etc.) with built-in:
- Circuit breaking
- Retry logic with jitter
- Performance monitoring
- Cost tracking
- Fallback providers

DESIGN GOALS:
1. Make it easy to swap providers
2. Centralize AI configuration
3. Automatic failover to backup providers
4. Comprehensive observability
5. Type-safe interfaces
"""
import logging
import base64
from typing import Dict, Any, Optional, List, Union, Literal
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from openai import OpenAI
from openai.types.chat import ChatCompletion

from backend.core.config import settings
from backend.services.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig, CircuitBreakerOpenError
from backend.services.enhanced_retry import enhanced_sync_retry, ErrorType
from backend.services.observability import track_ai_call, AIMetrics, log_ai_metrics, StructuredLogger

logger = StructuredLogger("ai_provider")


# =============================================================================
# TYPES AND ENUMS
# =============================================================================

class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"  # For future expansion


class AIModel(str, Enum):
    """Supported AI models."""
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT4_TURBO = "gpt-4-turbo"
    # Add more models as needed


@dataclass
class AIMessage:
    """Unified message format."""
    role: Literal["system", "user", "assistant"]
    content: Union[str, List[Dict[str, Any]]]  # String or multimodal content


@dataclass
class AICompletionRequest:
    """Request for AI completion."""
    messages: List[AIMessage]
    model: AIModel
    temperature: float = 0.7
    max_tokens: int = 1000
    response_format: Optional[Dict[str, Any]] = None
    timeout: int = 30

    # Vision-specific
    images: Optional[List[bytes]] = None


@dataclass
class AICompletionResponse:
    """Response from AI completion."""
    content: str
    model: str
    provider: AIProvider

    # Token usage
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    # Metadata
    request_id: Optional[str] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


# =============================================================================
# PROVIDER INTERFACE
# =============================================================================

class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, provider_name: str, circuit_breaker_name: str):
        """Initialize provider."""
        self.provider_name = provider_name
        self.circuit_breaker = get_circuit_breaker(
            circuit_breaker_name,
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=2
            )
        )
        self.logger = StructuredLogger(f"ai_provider.{provider_name}")

    @abstractmethod
    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """
        Generate completion.

        Args:
            request: Completion request

        Returns:
            Completion response

        Raises:
            Exception: On error
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


# =============================================================================
# OPENAI PROVIDER
# =============================================================================

class OpenAIProvider(BaseAIProvider):
    """OpenAI provider implementation."""

    def __init__(self):
        """Initialize OpenAI provider."""
        super().__init__(provider_name="openai", circuit_breaker_name="openai_api")

        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")

        # Optional gateway override. When OPENAI_BASE_URL is set (e.g. a SubGate
        # /v1 endpoint) the SDK talks to it instead of the vendor, and
        # OPENAI_API_KEY carries the gateway's consumer token. Unset -> the
        # vendor default, so existing deployments are unchanged.
        base_url = (getattr(settings, "OPENAI_BASE_URL", "") or "").strip() or None
        client_kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        # Log the endpoint (never the key) so which path is live is visible.
        self.logger.info(
            "OpenAI provider initialized",
            base_url=base_url or "https://api.openai.com/v1 (default)"
        )

    def _build_messages(self, request: AICompletionRequest) -> List[Dict[str, Any]]:
        """Build OpenAI message format."""
        messages = []

        for msg in request.messages:
            # Handle vision messages with images
            if isinstance(msg.content, list):
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        return messages

    @enhanced_sync_retry(
        max_attempts=3,
        base_delay=2.0,
        jitter=True,
        circuit_breaker=None  # We handle circuit breaker separately
    )
    def _make_api_call(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]],
        timeout: int
    ) -> ChatCompletion:
        """Make OpenAI API call with retry logic."""
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }

        if response_format:
            kwargs["response_format"] = response_format

        return self.client.chat.completions.create(**kwargs)

    @track_ai_call(model="openai", provider="openai", operation="completion")
    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """
        Generate completion using OpenAI.

        Args:
            request: Completion request

        Returns:
            Completion response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            Exception: On API error
        """
        # Build messages
        messages = self._build_messages(request)

        self.logger.info(
            f"OpenAI completion request: {request.model.value}",
            model=request.model.value,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            message_count=len(messages)
        )

        # Call with circuit breaker protection
        try:
            response = self.circuit_breaker.call(
                self._make_api_call,
                messages=messages,
                model=request.model.value,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format=request.response_format,
                timeout=request.timeout
            )

            # Extract response
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason

            # Build response
            ai_response = AICompletionResponse(
                content=content,
                model=response.model,
                provider=AIProvider.OPENAI,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                request_id=response.id,
                finish_reason=finish_reason,
                raw_response=response
            )

            self.logger.info(
                f"OpenAI completion success: {ai_response.total_tokens} tokens",
                tokens=ai_response.total_tokens,
                finish_reason=finish_reason
            )

            return ai_response

        except CircuitBreakerOpenError:
            self.logger.error(
                "OpenAI circuit breaker is OPEN - service unavailable",
                circuit_breaker_state="open"
            )
            raise

        except Exception as e:
            self.logger.error(
                f"OpenAI completion failed: {str(e)[:200]}",
                error_type=type(e).__name__,
                error_message=str(e)[:500],
                exc_info=True
            )
            raise

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        from backend.services.circuit_breaker import CircuitState
        state = self.circuit_breaker.get_state()
        return state == CircuitState.CLOSED


# =============================================================================
# AI SERVICE (MAIN INTERFACE)
# =============================================================================

class AIService:
    """
    Main AI service with automatic provider selection and fallback.

    Usage:
        ai = AIService()
        response = ai.complete(AICompletionRequest(...))
    """

    def __init__(self, primary_provider: AIProvider = AIProvider.OPENAI):
        """
        Initialize AI service.

        Args:
            primary_provider: Primary AI provider to use
        """
        self.logger = StructuredLogger("ai_service")
        self.providers: Dict[AIProvider, BaseAIProvider] = {}

        # Initialize OpenAI provider
        try:
            self.providers[AIProvider.OPENAI] = OpenAIProvider()
            self.logger.info("Initialized OpenAI provider")
        except Exception as e:
            self.logger.warning(f"Failed to initialize OpenAI provider: {e}")

        # Set primary provider
        self.primary_provider = primary_provider

        if not self.providers:
            raise RuntimeError("No AI providers available")

        self.logger.info(
            f"AI Service initialized with {len(self.providers)} provider(s)",
            providers=[p.value for p in self.providers.keys()],
            primary=primary_provider.value
        )

    def complete(
        self,
        request: AICompletionRequest,
        fallback: bool = True
    ) -> AICompletionResponse:
        """
        Generate completion with automatic fallback.

        Args:
            request: Completion request
            fallback: Whether to try fallback providers on failure

        Returns:
            Completion response

        Raises:
            Exception: If all providers fail
        """
        # Try primary provider first
        primary = self.providers.get(self.primary_provider)
        if primary:
            try:
                self.logger.info(
                    f"Attempting completion with primary provider: {self.primary_provider.value}",
                    provider=self.primary_provider.value,
                    model=request.model.value
                )
                return primary.complete(request)
            except CircuitBreakerOpenError:
                self.logger.warning(
                    f"Primary provider circuit breaker is open: {self.primary_provider.value}",
                    provider=self.primary_provider.value
                )
                if not fallback:
                    raise
            except Exception as e:
                self.logger.error(
                    f"Primary provider failed: {self.primary_provider.value} - {str(e)[:200]}",
                    provider=self.primary_provider.value,
                    error_type=type(e).__name__,
                    exc_info=True
                )
                if not fallback:
                    raise

        # Try fallback providers if enabled
        if fallback:
            for provider_type, provider in self.providers.items():
                if provider_type == self.primary_provider:
                    continue  # Already tried

                if not provider.is_available():
                    self.logger.warning(
                        f"Fallback provider not available: {provider_type.value}",
                        provider=provider_type.value
                    )
                    continue

                try:
                    self.logger.info(
                        f"Attempting completion with fallback provider: {provider_type.value}",
                        provider=provider_type.value,
                        model=request.model.value
                    )
                    return provider.complete(request)
                except Exception as e:
                    self.logger.error(
                        f"Fallback provider failed: {provider_type.value} - {str(e)[:200]}",
                        provider=provider_type.value,
                        error_type=type(e).__name__,
                        exc_info=True
                    )
                    continue

        # All providers failed
        self.logger.critical(
            "All AI providers failed",
            providers_attempted=[p.value for p in self.providers.keys()]
        )
        raise RuntimeError("All AI providers failed. Please try again later.")

    def create_vision_request(
        self,
        prompt: str,
        image_bytes: bytes,
        model: AIModel = AIModel.GPT4O,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, Any]] = None
    ) -> AICompletionRequest:
        """
        Create a vision request for image analysis.

        Args:
            prompt: Text prompt
            image_bytes: Image bytes
            model: AI model to use
            temperature: Temperature (0-2)
            max_tokens: Max tokens to generate
            response_format: Response format (e.g., {"type": "json_object"})

        Returns:
            Completion request
        """
        # Encode image
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Create message with vision content
        message = AIMessage(
            role="user",
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": "high"
                    }
                }
            ]
        )

        return AICompletionRequest(
            messages=[message],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            images=[image_bytes]
        )

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        status = {}
        for provider_type, provider in self.providers.items():
            status[provider_type.value] = {
                "available": provider.is_available(),
                "circuit_breaker_state": provider.circuit_breaker.get_state().value,
                "metrics": provider.circuit_breaker.get_metrics()
            }
        return status


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

# Lazy initialization
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """
    Get global AI service instance.

    Returns:
        AI service instance
    """
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService(primary_provider=AIProvider.OPENAI)
    return _ai_service
