"""
Health check and monitoring endpoints.

Provides comprehensive health checks for:
- AI providers (OpenAI, etc.)
- Database connectivity
- Redis connectivity
- Circuit breaker status
- System metrics
"""
import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime

from backend.services.circuit_breaker import get_all_circuit_breaker_metrics
from backend.queue.queue_connection import get_redis_connection
from backend.db.session import SessionLocal
from backend.services.observability import StructuredLogger

logger = StructuredLogger("health_check")

router = APIRouter(prefix="/health", tags=["health"])


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class ComponentHealth(BaseModel):
    """Health status of a component."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Dict[str, Any] = {}


class HealthCheckResponse(BaseModel):
    """Overall health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    uptime_seconds: Optional[float] = None
    components: Dict[str, ComponentHealth]


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status."""
    name: str
    state: str
    metrics: Dict[str, Any]


class MonitoringResponse(BaseModel):
    """Monitoring dashboard response."""
    timestamp: str
    circuit_breakers: Dict[str, CircuitBreakerStatus]
    system_status: Dict[str, Any]


# =============================================================================
# HEALTH CHECK FUNCTIONS
# =============================================================================

def check_database_health() -> ComponentHealth:
    """Check database connectivity."""
    start_time = time.time()

    try:
        db = SessionLocal()
        try:
            # Simple query to test connectivity (SQLAlchemy 2.x requires text())
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            latency_ms = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="database",
                status="healthy",
                latency_ms=round(latency_ms, 2)
            )
        finally:
            db.close()

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Database health check failed: {e}", exc_info=True)

        return ComponentHealth(
            name="database",
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e)[:200]
        )


def check_redis_health() -> ComponentHealth:
    """Check Redis connectivity."""
    start_time = time.time()

    try:
        redis_client = get_redis_connection()
        if not redis_client:
            return ComponentHealth(
                name="redis",
                status="degraded",
                error="Redis client not initialized"
            )

        # Test ping
        redis_client.ping()
        latency_ms = (time.time() - start_time) * 1000

        # Get info
        info = redis_client.info("server")

        return ComponentHealth(
            name="redis",
            status="healthy",
            latency_ms=round(latency_ms, 2),
            details={
                "version": info.get("redis_version", "unknown"),
                "uptime_days": info.get("uptime_in_days", 0)
            }
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Redis health check failed: {e}", exc_info=True)

        return ComponentHealth(
            name="redis",
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e)[:200]
        )


def check_ai_providers_health() -> ComponentHealth:
    """Check AI providers status."""
    start_time = time.time()

    try:
        from backend.services.ai_provider import get_ai_service

        ai_service = get_ai_service()
        provider_status = ai_service.get_provider_status()

        # Determine overall status
        all_healthy = all(
            p["available"] and p["circuit_breaker_state"] == "closed"
            for p in provider_status.values()
        )

        any_available = any(
            p["available"]
            for p in provider_status.values()
        )

        if all_healthy:
            overall_status = "healthy"
        elif any_available:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        latency_ms = (time.time() - start_time) * 1000

        return ComponentHealth(
            name="ai_providers",
            status=overall_status,
            latency_ms=round(latency_ms, 2),
            details=provider_status
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"AI providers health check failed: {e}", exc_info=True)

        return ComponentHealth(
            name="ai_providers",
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e)[:200]
        )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
def health_check():
    """
    Comprehensive health check endpoint.

    Returns health status of all system components:
    - Database
    - Redis
    - AI Providers (OpenAI, etc.)
    - Circuit breakers

    Status values:
    - "healthy": All components operational
    - "degraded": Some components have issues but system is functional
    - "unhealthy": Critical components are down
    """
    components = {}

    # Check database
    components["database"] = check_database_health()

    # Check Redis
    components["redis"] = check_redis_health()

    # Check AI providers
    components["ai_providers"] = check_ai_providers_health()

    # Determine overall status
    if all(c.status == "healthy" for c in components.values()):
        overall_status = "healthy"
    elif any(c.status == "unhealthy" for c in components.values()):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        components=components
    )


@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness_check():
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if service is ready to accept traffic.
    Returns 503 if service is not ready.
    """
    # Check critical components
    db_health = check_database_health()

    if db_health.status == "unhealthy":
        return {
            "ready": False,
            "reason": "Database unhealthy"
        }, status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": True,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness_check():
    """
    Kubernetes liveness probe endpoint.

    Always returns 200 if the service is running.
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/monitoring", response_model=MonitoringResponse)
def monitoring_dashboard():
    """
    Monitoring dashboard with detailed metrics.

    Provides:
    - Circuit breaker states and metrics
    - System performance metrics
    - Component health details
    """
    # Get circuit breaker metrics
    cb_metrics = get_all_circuit_breaker_metrics()

    circuit_breakers = {}
    for name, metrics in cb_metrics.items():
        circuit_breakers[name] = CircuitBreakerStatus(
            name=name,
            state=metrics.get("state", "unknown"),
            metrics=metrics
        )

    # Get system status
    system_status = {
        "database": check_database_health().dict(),
        "redis": check_redis_health().dict(),
        "ai_providers": check_ai_providers_health().dict()
    }

    return MonitoringResponse(
        timestamp=datetime.utcnow().isoformat(),
        circuit_breakers=circuit_breakers,
        system_status=system_status
    )


@router.post("/circuit-breakers/reset", status_code=status.HTTP_200_OK)
def reset_circuit_breakers():
    """
    Reset all circuit breakers to CLOSED state.

    WARNING: Use with caution. Only reset if you're sure the underlying
    issues have been resolved.
    """
    from backend.services.circuit_breaker import _registry

    try:
        _registry.reset_all()
        logger.info("All circuit breakers reset manually")

        return {
            "success": True,
            "message": "All circuit breakers reset to CLOSED state",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to reset circuit breakers: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
