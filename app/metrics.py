"""Prometheus metrics for Risk API service"""
import time
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from fastapi import Request
from fastapi.responses import Response
import logging

logger = logging.getLogger(__name__)

# Custom metrics for Risk API
ticker_requests_total = Counter(
    'risk_api_ticker_requests_total',
    'Total number of ticker requests',
    ['ticker', 'endpoint']
)

portfolio_operations_total = Counter(
    'risk_api_portfolio_operations_total',
    'Total portfolio operations',
    ['operation', 'user_id']
)

cache_operations_total = Counter(
    'risk_api_cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type']
)

active_user_sessions = Gauge(
    'risk_api_active_user_sessions',
    'Number of active user sessions'
)

ticker_processing_duration = Histogram(
    'risk_api_ticker_processing_seconds',
    'Time spent processing ticker requests',
    ['ticker']
)

redis_operations_total = Counter(
    'risk_api_redis_operations_total',
    'Total Redis operations',
    ['operation', 'channel']
)

database_operations_total = Counter(
    'risk_api_database_operations_total',
    'Total database operations',
    ['operation', 'table']
)


def setup_metrics(app):
    """Set up Prometheus metrics instrumentation for FastAPI app"""
    
    # Set up the instrumentator with custom metrics
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/healthz", "/favicon.ico"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="risk_api_inprogress",
        inprogress_labels=True,
    )
    
    # Add standard metrics
    instrumentator.add(metrics.request_size())
    instrumentator.add(metrics.response_size())
    instrumentator.add(metrics.latency())
    instrumentator.add(metrics.requests())
    
    # Add custom metric for tracking endpoint usage
    @instrumentator.add()
    def track_endpoint_usage(info: metrics.Info):
        endpoint = info.request.url.path
        method = info.request.method
        status = info.response.status_code
        
        # Track API endpoint usage
        if endpoint.startswith('/ticker/'):
            ticker = endpoint.split('/')[-1].upper()
            ticker_requests_total.labels(ticker=ticker, endpoint='ticker_info').inc()
        elif endpoint.startswith('/search'):
            ticker_requests_total.labels(ticker='search', endpoint='search').inc()
        elif endpoint.startswith('/portfolio'):
            # Extract operation from method and path
            if method == 'GET':
                operation = 'read'
            elif method == 'POST':
                operation = 'create'
            elif method == 'PUT':
                operation = 'update'
            elif method == 'DELETE':
                operation = 'delete'
            else:
                operation = 'unknown'
            
            user_id = getattr(info.request.state, 'user_id', 'anonymous')
            portfolio_operations_total.labels(operation=operation, user_id=str(user_id)).inc()
    
    # Initialize instrumentator
    instrumentator.instrument(app)
    
    return instrumentator


def track_ticker_processing(ticker: str):
    """Decorator to track ticker processing time"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                ticker_processing_duration.labels(ticker=ticker).observe(duration)
        return wrapper
    return decorator


def track_cache_operation(operation: str, cache_type: str):
    """Track cache operations"""
    cache_operations_total.labels(operation=operation, cache_type=cache_type).inc()


def track_redis_operation(operation: str, channel: str):
    """Track Redis operations"""
    redis_operations_total.labels(operation=operation, channel=channel).inc()


def track_database_operation(operation: str, table: str):
    """Track database operations"""
    database_operations_total.labels(operation=operation, table=table).inc()


def update_active_sessions(count: int):
    """Update active user sessions gauge"""
    active_user_sessions.set(count)


async def metrics_endpoint():
    """Expose Prometheus metrics endpoint"""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    ) 