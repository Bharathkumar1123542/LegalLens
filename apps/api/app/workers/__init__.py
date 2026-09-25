"""
Workers — LegalLens Background Job Processing

Centralized Celery app configuration for async task processing.
Used across: ingestion, clause extraction, embedding, comparison, export.

Architecture:
- Celery broker/backend: Redis
- Task routing: all tasks in same queue for now (can split later)
- Retry policy: 3 retries with exponential backoff
- Time limits: 30 minutes hard, 25 minutes soft

Usage:
    from app.workers import celery_app
    
    @celery_app.task(name="my_task", bind=True)
    def my_task(self, arg1, arg2):
        # Task implementation
        pass
    
    # In API endpoint:
    my_task.delay(arg1, arg2)
"""

from __future__ import annotations

from celery import Celery, Task
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "legallens",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes hard limit
    task_soft_time_limit=1500,  # 25 minutes soft limit
    task_acks_late=True,  # Acknowledge after task completion
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    task_reject_on_worker_lost=True,  # Re-queue if worker dies
    broker_connection_retry_on_startup=True,
)


class AsyncTask(Task):
    """
    Base task class for async operations with SQLAlchemy.
    
    Provides a run_async() method that can be overridden in subclasses
    to implement async logic. The __call__ method wraps this in asyncio.run().
    
    Example:
        @celery_app.task(base=AsyncTask, bind=True, max_retries=3)
        class MyTask(AsyncTask):
            async def run_async(self, arg1):
                async with get_async_session() as db:
                    # Async database operations
                    pass
    """
    
    async def run_async(self, *args, **kwargs):
        """Override in subclass to implement async logic."""
        raise NotImplementedError("Subclass must implement run_async()")
    
    def __call__(self, *args, **kwargs):
        """Sync wrapper that runs async code using asyncio.run()."""
        import asyncio
        return asyncio.run(self.run_async(*args, **kwargs))


# Task routing configuration (can expand for queue separation)
celery_app.conf.task_routes = {
    "process_document": {"queue": "ingestion"},
    "embed_document": {"queue": "embedding"},
    "extract_clauses": {"queue": "extraction"},
    "run_comparison": {"queue": "comparison"},
    "generate_export": {"queue": "export"},
}

__all__ = ["celery_app", "AsyncTask"]
