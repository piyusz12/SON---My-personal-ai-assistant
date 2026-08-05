# core/pipeline.py — Parallel CPU Pipeline Orchestrator for SON V3
"""
Manages thread pools and process pools to fully utilize the
Ryzen 7 7840HS (8 cores / 16 threads).

Design:
    - ThreadPoolExecutor (8 workers): I/O-bound tasks (network, file reads, Ollama API)
    - ProcessPoolExecutor (4 workers): CPU-bound tasks (chunking, hashing, scanning)
    - Named task queues prevent any subsystem from starving others
    
Usage:
    from core.pipeline import Pipeline
    
    pipeline = Pipeline()
    future = pipeline.submit_io(my_function, arg1, arg2)
    result = future.result(timeout=10)
    
    # Or batch:
    results = pipeline.map_cpu(process_chunk, chunk_list)
"""
import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future
from typing import Callable, Any, Iterable

from core.config import Config

logger = Config.get_logger(__name__)


class Pipeline:
    """
    Central parallel execution engine for SON V3.
    
    Distributes work across CPU cores to maximize utilization
    of the Ryzen 7 7840HS while preventing resource starvation.
    """
    
    # Worker counts tuned for 8C/16T Ryzen 7 7840HS
    IO_WORKERS = 8      # I/O-bound: matches physical cores
    CPU_WORKERS = 4      # CPU-bound: half cores (GIL-free via multiprocessing)
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton — one pipeline per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._io_pool = ThreadPoolExecutor(
            max_workers=self.IO_WORKERS,
            thread_name_prefix="son-io"
        )
        self._cpu_pool = ProcessPoolExecutor(
            max_workers=self.CPU_WORKERS,
        )
        
        # Task tracking
        self._active_tasks: dict[str, list[Future]] = {
            "audio": [],
            "embedding": [],
            "codebase": [],
            "system": [],
            "llm": [],
            "general": [],
        }
        self._task_lock = threading.Lock()
        
        self._initialized = True
        logger.info(
            f"Pipeline initialized: {self.IO_WORKERS} I/O threads, "
            f"{self.CPU_WORKERS} CPU processes"
        )
    
    # ── I/O-Bound Task Submission ────────────────────────────────
    
    def submit_io(self, fn: Callable, *args, 
                  category: str = "general", **kwargs) -> Future:
        """
        Submit an I/O-bound task to the thread pool.
        
        Use for: Ollama API calls, file reads, network requests,
                 ChromaDB queries, Docker/service checks.
        
        Args:
            fn: Function to execute.
            category: Task category for tracking.
            *args, **kwargs: Arguments to pass to fn.
        
        Returns:
            Future object for the result.
        """
        future = self._io_pool.submit(fn, *args, **kwargs)
        self._track_task(category, future)
        return future
    
    # ── CPU-Bound Task Submission ────────────────────────────────
    
    def submit_cpu(self, fn: Callable, *args,
                   category: str = "general", **kwargs) -> Future:
        """
        Submit a CPU-bound task to the process pool.
        
        Use for: Code chunking, file scanning, hashing,
                 audio preprocessing, text analysis.
        
        Note: fn and args must be picklable (no lambdas, closures,
              or unpicklable objects).
        
        Args:
            fn: Picklable function to execute.
            category: Task category for tracking.
            *args: Positional arguments to pass to fn.
        
        Returns:
            Future object for the result.
        """
        future = self._cpu_pool.submit(fn, *args, **kwargs)
        self._track_task(category, future)
        return future
    
    def map_cpu(self, fn: Callable, items: Iterable, 
                chunksize: int = 4) -> list:
        """
        Map a function across items using the CPU process pool.
        
        Equivalent to multiprocessing.Pool.map() but integrated
        with the pipeline.
        
        Args:
            fn: Picklable function.
            items: Iterable of arguments.
            chunksize: Batch size per process.
        
        Returns:
            List of results in order.
        """
        return list(self._cpu_pool.map(fn, items, chunksize=chunksize))
    
    def map_io(self, fn: Callable, items: Iterable) -> list:
        """
        Map a function across items using the I/O thread pool.
        
        Args:
            fn: Function to call for each item.
            items: Iterable of arguments.
        
        Returns:
            List of results in order.
        """
        return list(self._io_pool.map(fn, items))
    
    # ── Batch Submission ─────────────────────────────────────────
    
    def submit_batch_io(self, fn: Callable, args_list: list[tuple],
                        category: str = "general") -> list[Future]:
        """
        Submit multiple I/O tasks at once.
        
        Args:
            fn: Function to execute for each set of args.
            args_list: List of argument tuples.
            category: Task category.
        
        Returns:
            List of Future objects.
        """
        futures = []
        for args in args_list:
            future = self._io_pool.submit(fn, *args)
            self._track_task(category, future)
            futures.append(future)
        return futures
    
    # ── Task Tracking ────────────────────────────────────────────
    
    def _track_task(self, category: str, future: Future):
        """Track a task future for monitoring."""
        with self._task_lock:
            if category not in self._active_tasks:
                self._active_tasks[category] = []
            self._active_tasks[category].append(future)
            
            # Clean completed futures periodically
            self._active_tasks[category] = [
                f for f in self._active_tasks[category] if not f.done()
            ]
    
    def get_active_count(self, category: str = None) -> int:
        """Get count of active (pending/running) tasks."""
        with self._task_lock:
            if category:
                tasks = self._active_tasks.get(category, [])
                return sum(1 for f in tasks if not f.done())
            return sum(
                sum(1 for f in tasks if not f.done())
                for tasks in self._active_tasks.values()
            )
    
    def get_stats(self) -> dict:
        """Get pipeline utilization statistics."""
        with self._task_lock:
            stats = {
                "io_workers": self.IO_WORKERS,
                "cpu_workers": self.CPU_WORKERS,
                "active_tasks": {},
            }
            for category, tasks in self._active_tasks.items():
                active = sum(1 for f in tasks if not f.done())
                if active > 0:
                    stats["active_tasks"][category] = active
            return stats
    
    # ── Shutdown ─────────────────────────────────────────────────
    
    def shutdown(self, wait: bool = True):
        """Gracefully shut down all pools."""
        logger.info("Pipeline shutting down...")
        self._io_pool.shutdown(wait=wait)
        self._cpu_pool.shutdown(wait=wait)
        logger.info("Pipeline shutdown complete.")
