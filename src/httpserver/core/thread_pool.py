"""
=============================================================================
THREAD POOL IMPLEMENTATION
=============================================================================

A thread pool manages a group of worker threads that process tasks from
a shared queue. This is a fundamental concurrency pattern used in many
production systems.

=============================================================================
WHY USE A THREAD POOL?
=============================================================================

Without a thread pool, you might create a new thread for each connection:

    BAD APPROACH (Thread-per-connection without pool):
    ─────────────────────────────────────────────────
    
    for connection in accept_connections():
        thread = Thread(target=handle, args=(connection,))
        thread.start()
    
    Problems:
    1. Thread creation is EXPENSIVE (~1ms + memory allocation)
    2. No limit on concurrent threads → resource exhaustion
    3. 10,000 connections = 10,000 threads = crash!
    4. No reuse of threads → constant overhead

    GOOD APPROACH (Thread pool):
    ────────────────────────────
    
    pool = ThreadPool(min_workers=4, max_workers=16)
    pool.start()
    
    for connection in accept_connections():
        pool.submit(handle, args=(connection,))
    
    Benefits:
    1. Workers are created once, reused many times
    2. Limit on concurrent work (max_workers)
    3. Tasks queue up when busy → graceful degradation
    4. Predictable resource usage

=============================================================================
THREAD POOL ARCHITECTURE
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Thread Pool                                   │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   ┌─────────────────────────────────────────────────────────────┐   │
    │   │                      TASK QUEUE                              │   │
    │   │  ─────────────────────────────────────────────────────────  │   │
    │   │  [Task 1] [Task 2] [Task 3] [Task 4] ...                    │   │
    │   │                                                              │   │
    │   │  • Thread-safe queue (queue.Queue)                          │   │
    │   │  • Blocks when empty (workers wait)                         │   │
    │   │  • Blocks when full (submit waits)                          │   │
    │   │  • FIFO order (first in, first out)                         │   │
    │   └──────────────────────┬──────────────────────────────────────┘   │
    │                          │                                           │
    │                          │ pull()                                    │
    │                          ▼                                           │
    │   ┌─────────────────────────────────────────────────────────────┐   │
    │   │                      WORKERS                                 │   │
    │   │  ─────────────────────────────────────────────────────────  │   │
    │   │                                                              │   │
    │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
    │   │  │ Worker 1 │ │ Worker 2 │ │ Worker 3 │ │ Worker 4 │       │   │
    │   │  │ (idle)   │ │ (busy)   │ │ (busy)   │ │ (idle)   │       │   │
    │   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
    │   │                                                              │   │
    │   │  • Each worker is a daemon thread                           │   │
    │   │  • Pulls tasks from queue                                   │   │
    │   │  • Executes task.func(*task.args, **task.kwargs)           │   │
    │   │  • Goes back to waiting for next task                       │   │
    │   └─────────────────────────────────────────────────────────────┘   │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

=============================================================================
WORKER LIFECYCLE
=============================================================================

    Worker Thread:
    ─────────────
    
    def run(self):
        while not shutdown:
            task = queue.get()      ← BLOCKS until task available
            if task is None:        ← "Poison pill" signals shutdown
                break
            execute(task)           ← Run the task
            queue.task_done()       ← Mark task complete
    
    The "poison pill" pattern:
    ─────────────────────────
    
    To shut down workers cleanly, we put None (a "poison pill") in the queue.
    When a worker gets None, it knows to exit its loop and terminate.
    
        pool.shutdown()
            └─ for each worker: queue.put(None)
            └─ workers receive None and exit

=============================================================================
SCALING UP/DOWN
=============================================================================

The pool can dynamically adjust its size:

    MIN_WORKERS (4):
        └─ Always running, even when idle
        └─ Ready to handle bursts immediately
        └─ Created at startup

    MAX_WORKERS (16):
        └─ Limit to prevent resource exhaustion
        └─ More workers spawned as queue fills up
        └─ Workers exit when idle (not implemented in this basic version)

    SCALING TRIGGER:
        └─ All workers busy AND tasks in queue?
        └─ If workers < max_workers: add worker

=============================================================================
COMMON INTERVIEW QUESTIONS
=============================================================================

Q: Why not create unlimited threads?
A: Memory! Each thread has a stack (1-8 MB). 1000 threads = 1-8 GB RAM.
   Plus context switching overhead when CPU switches between threads.

Q: How do you handle a slow task blocking the pool?
A: Use timeouts. If a task exceeds timeout, log and skip (task is abandoned).
   In production, you might use separate pools for fast/slow operations.

Q: What happens when the queue is full?
A: Either block (wait for space), drop the task, or return error.
   In HTTP servers, returning 503 Service Unavailable is appropriate.

Q: Thread pool vs async/await?
A: Threads are simpler but use more memory.
   Async is more scalable but harder to reason about.
   For I/O-bound work (HTTP), either works well.
   For CPU-bound work, need multiprocessing (GIL limitation).

=============================================================================
"""

import threading
import queue
import time
import logging
from typing import Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """
    Worker thread states.
    
    Used for monitoring and debugging the thread pool.
    """
    IDLE = "idle"      # Waiting for task
    BUSY = "busy"      # Executing task
    STOPPED = "stopped"  # Thread exited


@dataclass
class Task:
    """
    Represents a task to be executed by the thread pool.
    
    A task is essentially a deferred function call:
    "Call this function with these arguments later"
    
    Attributes:
        func: The function to execute.
        args: Positional arguments for the function.
        kwargs: Keyword arguments for the function.
        timeout: Maximum execution time (not enforced, just tracked).
        submitted_at: Time the task was submitted (for staleness check).
    """
    func: Callable[..., Any]
    args: tuple = ()
    kwargs: dict = None
    timeout: Optional[float] = None
    submitted_at: float = 0.0
    
    def __post_init__(self):
        """Set defaults for optional fields."""
        if self.kwargs is None:
            self.kwargs = {}
        if self.submitted_at == 0.0:
            self.submitted_at = time.time()


class Worker(threading.Thread):
    """
    Worker thread that processes tasks from the queue.
    
    Each worker:
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Worker Loop                                   │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   1. Wait for task from queue (blocking)                            │
    │          │                                                           │
    │          ▼                                                           │
    │   2. Check if it's a "poison pill" (None)                           │
    │          │                                                           │
    │          ├── Yes → Exit loop, thread terminates                     │
    │          │                                                           │
    │          └── No → Continue to step 3                                │
    │                                                                      │
    │   3. Execute the task                                               │
    │          │                                                           │
    │          ├── Try: task.func(*task.args, **task.kwargs)             │
    │          │                                                           │
    │          └── Catch: Log any exceptions (don't crash worker)         │
    │                                                                      │
    │   4. Signal task complete (task_done())                             │
    │          │                                                           │
    │          └── Go back to step 1                                       │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
    """
    
    def __init__(
        self,
        task_queue: queue.Queue,
        worker_id: int,
        idle_timeout: float = 60.0
    ):
        """
        Initialize the worker.
        
        Args:
            task_queue: Queue to pull tasks from.
            worker_id: Unique identifier for this worker (for logging).
            idle_timeout: Seconds to wait for task before checking shutdown.
        """
        # daemon=True: Thread exits when main program exits
        # This prevents workers from keeping the program alive
        super().__init__(name=f"Worker-{worker_id}", daemon=True)
        
        self.task_queue = task_queue
        self.worker_id = worker_id
        self.idle_timeout = idle_timeout
        
        # State tracking
        self.state = WorkerState.IDLE
        self._shutdown = threading.Event()  # For signaling shutdown
        self._current_task: Optional[Task] = None
        
        # Metrics
        self.tasks_completed = 0
        self.tasks_failed = 0
    
    def run(self):
        """
        Main worker loop.
        
        This is the entry point when the thread starts.
        It runs until shutdown is signaled or a poison pill is received.
        """
        logger.debug(f"Worker {self.worker_id} started")
        
        while not self._shutdown.is_set():
            try:
                # ─────────────────────────────────────────────────────────
                # WAIT FOR TASK
                # ─────────────────────────────────────────────────────────
                # queue.get() blocks until a task is available.
                # We use a timeout so we can periodically check for shutdown.
                
                task = self.task_queue.get(timeout=self.idle_timeout)
                
                # ─────────────────────────────────────────────────────────
                # CHECK FOR POISON PILL
                # ─────────────────────────────────────────────────────────
                # None is the "poison pill" that signals shutdown.
                # When we get it, we break out of the loop and exit.
                
                if task is None:
                    break
                
                # ─────────────────────────────────────────────────────────
                # EXECUTE TASK
                # ─────────────────────────────────────────────────────────
                self._execute_task(task)
                
                # ─────────────────────────────────────────────────────────
                # MARK TASK COMPLETE
                # ─────────────────────────────────────────────────────────
                # This is important for queue.join() to work properly.
                # It decrements the "unfinished tasks" counter.
                
                self.task_queue.task_done()
                
            except queue.Empty:
                # ─────────────────────────────────────────────────────────
                # NO TASK AVAILABLE
                # ─────────────────────────────────────────────────────────
                # This is normal - just means no tasks for idle_timeout seconds.
                # We check for shutdown and loop again.
                continue
                
            except Exception as e:
                # Catch any unexpected errors to keep worker running
                logger.exception(f"Worker {self.worker_id} error: {e}")
        
        self.state = WorkerState.STOPPED
        logger.debug(f"Worker {self.worker_id} stopped")
    
    def _execute_task(self, task: Task):
        """
        Execute a single task.
        
        This is where the actual work happens. We wrap it with:
        - State tracking (BUSY while executing)
        - Timing (for performance monitoring)
        - Exception handling (don't crash the worker)
        - Staleness check (skip tasks that waited too long)
        
        Args:
            task: The task to execute.
        """
        self.state = WorkerState.BUSY
        self._current_task = task
        start_time = time.time()
        
        try:
            # ─────────────────────────────────────────────────────────────
            # CHECK IF TASK IS STALE
            # ─────────────────────────────────────────────────────────────
            # If a task has been waiting longer than its timeout,
            # it's already "expired" - don't bother executing it.
            # This can happen under heavy load.
            
            if task.timeout and (start_time - task.submitted_at) > task.timeout:
                wait_time = start_time - task.submitted_at
                logger.warning(
                    f"Task timed out before execution "
                    f"(waited {wait_time:.2f}s, timeout was {task.timeout}s)"
                )
                self.tasks_failed += 1
                return
            
            # ─────────────────────────────────────────────────────────────
            # EXECUTE THE TASK
            # ─────────────────────────────────────────────────────────────
            # This is the actual function call that was submitted.
            # For HTTP server, this is handle_connection(connection).
            
            task.func(*task.args, **task.kwargs)
            
            elapsed = time.time() - start_time
            logger.debug(f"Worker {self.worker_id} completed task in {elapsed:.3f}s")
            self.tasks_completed += 1
            
        except Exception as e:
            # ─────────────────────────────────────────────────────────────
            # HANDLE TASK FAILURE
            # ─────────────────────────────────────────────────────────────
            # We catch ALL exceptions here because:
            # 1. We don't want one bad task to crash the worker
            # 2. The worker should keep processing other tasks
            # 3. We log the error for debugging
            
            elapsed = time.time() - start_time
            logger.exception(
                f"Worker {self.worker_id} task failed after {elapsed:.3f}s: {e}"
            )
            self.tasks_failed += 1
        
        finally:
            # Always reset state, even if task failed
            self.state = WorkerState.IDLE
            self._current_task = None
    
    def shutdown(self):
        """Signal the worker to stop."""
        self._shutdown.set()


class ThreadPool:
    """
    Thread pool for concurrent task execution.
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      ThreadPool Usage                                │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   # Create pool                                                      │
    │   pool = ThreadPool(min_workers=4, max_workers=16)                  │
    │                                                                      │
    │   # Start workers                                                    │
    │   pool.start()                                                       │
    │                                                                      │
    │   # Submit tasks                                                     │
    │   pool.submit(handle_connection, args=(conn,))                      │
    │   pool.submit(process_data, args=(data,), timeout=30)               │
    │                                                                      │
    │   # Check status                                                     │
    │   print(pool.stats)  # {"workers": {"busy": 3, ...}, ...}          │
    │                                                                      │
    │   # Shutdown (waits for pending tasks)                              │
    │   pool.shutdown(wait=True)                                          │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
    
    Features:
    - Configurable worker count (min and max)
    - Task queue with size limit (prevents memory explosion)
    - Graceful shutdown (wait for tasks to complete)
    - Auto-scaling (add workers when queue is backing up)
    - Worker health monitoring
    """
    
    def __init__(
        self,
        min_workers: int = 4,
        max_workers: int = 16,
        queue_size: int = 100,
        idle_timeout: float = 60.0
    ):
        """
        Initialize the thread pool.
        
        Args:
            min_workers: Minimum number of worker threads.
                         These are created at startup and always running.
                         
            max_workers: Maximum number of worker threads.
                         More can be spawned under load, up to this limit.
                         
            queue_size: Maximum size of the task queue.
                        If queue is full, submit() will block or fail.
                        This prevents unlimited memory growth.
                        
            idle_timeout: Seconds before idle workers check for shutdown.
                          Also used for scaling down (not implemented here).
        """
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.queue_size = queue_size
        self.idle_timeout = idle_timeout
        
        # ─────────────────────────────────────────────────────────────────
        # THE TASK QUEUE
        # ─────────────────────────────────────────────────────────────────
        # This is the heart of the thread pool.
        # Tasks go in, workers pull them out.
        #
        # queue.Queue is thread-safe by design:
        # - Multiple threads can put/get simultaneously
        # - No need for manual locking
        # - Blocks when empty (get) or full (put)
        
        self._task_queue: queue.Queue[Optional[Task]] = queue.Queue(maxsize=queue_size)
        
        # Worker management
        self._workers: list[Worker] = []
        self._lock = threading.Lock()  # Protects _workers list
        self._started = False
        self._shutdown = False
        self._next_worker_id = 0
    
    def start(self):
        """
        Start the thread pool with minimum workers.
        
        This creates the initial set of worker threads.
        They start immediately and begin waiting for tasks.
        """
        if self._started:
            return  # Already started
        
        logger.info(f"Starting thread pool with {self.min_workers} workers")
        
        # Create minimum number of workers
        for _ in range(self.min_workers):
            self._add_worker()
        
        self._started = True
    
    def _add_worker(self) -> Worker:
        """
        Add a new worker to the pool.
        
        Creates a new Worker thread and starts it immediately.
        Uses a lock to prevent race conditions when scaling up.
        """
        with self._lock:
            if len(self._workers) >= self.max_workers:
                raise RuntimeError("Maximum workers reached")
            
            worker = Worker(
                task_queue=self._task_queue,
                worker_id=self._next_worker_id,
                idle_timeout=self.idle_timeout
            )
            self._next_worker_id += 1
            self._workers.append(worker)
            worker.start()
            return worker
    
    def submit(
        self,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict = None,
        timeout: Optional[float] = None,
        block: bool = True,
        queue_timeout: Optional[float] = None
    ) -> bool:
        """
        Submit a task for execution.
        
        ┌─────────────────────────────────────────────────────────────────┐
        │                    submit() Flow                                 │
        ├─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │   1. Create Task object                                         │
        │          │                                                       │
        │          ▼                                                       │
        │   2. Try to put in queue                                        │
        │          │                                                       │
        │          ├── Queue has space → Success!                         │
        │          │                                                       │
        │          └── Queue full:                                        │
        │                  │                                               │
        │                  ├── block=True → Wait for space                │
        │                  │                                               │
        │                  └── block=False → Return False (rejected)      │
        │                                                                  │
        │   3. Maybe scale up (if all workers busy)                       │
        │          │                                                       │
        │          ▼                                                       │
        │   4. Return True (task accepted)                                │
        │                                                                  │
        └─────────────────────────────────────────────────────────────────┘
        
        Args:
            func: The function to execute.
            args: Positional arguments for the function.
            kwargs: Keyword arguments for the function.
            timeout: Maximum execution time in seconds.
            block: Whether to block if queue is full.
            queue_timeout: How long to wait if queue is full.
        
        Returns:
            True if task was submitted, False if queue was full.
        
        Raises:
            RuntimeError: If pool is not started or is shutting down.
        """
        if not self._started:
            raise RuntimeError("Thread pool not started")
        
        if self._shutdown:
            raise RuntimeError("Thread pool is shutting down")
        
        # Create the task
        task = Task(
            func=func,
            args=args,
            kwargs=kwargs or {},
            timeout=timeout
        )
        
        try:
            # ─────────────────────────────────────────────────────────────
            # PUT TASK IN QUEUE
            # ─────────────────────────────────────────────────────────────
            # If block=True and queue is full, this waits for space.
            # If block=False and queue is full, raises queue.Full.
            
            self._task_queue.put(task, block=block, timeout=queue_timeout)
            
            # ─────────────────────────────────────────────────────────────
            # MAYBE SCALE UP
            # ─────────────────────────────────────────────────────────────
            # If all workers are busy and queue is growing, add a worker.
            
            self._maybe_scale_up()
            
            return True
            
        except queue.Full:
            # Queue is full and we're not blocking
            return False
    
    def _maybe_scale_up(self):
        """
        Add workers if queue is backing up and we're under max.
        
        This is a simple scaling heuristic:
        - If ALL workers are busy (none idle)
        - AND there are tasks waiting in the queue
        - AND we haven't reached max_workers
        → Spawn another worker
        
        More sophisticated implementations might consider:
        - Average queue wait time
        - Historical patterns
        - Gradual scale-down when idle
        """
        with self._lock:
            # Count busy workers
            busy_count = sum(1 for w in self._workers if w.state == WorkerState.BUSY)
            
            # All busy and more work waiting?
            if busy_count == len(self._workers) and len(self._workers) < self.max_workers:
                queue_size = self._task_queue.qsize()
                if queue_size > 0:
                    logger.debug(
                        f"Scaling up: {len(self._workers)} -> {len(self._workers) + 1} workers"
                    )
                    self._add_worker()
    
    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Shutdown the thread pool.
        
        ┌─────────────────────────────────────────────────────────────────┐
        │                    shutdown() Flow                               │
        ├─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │   1. Mark as shutting down (reject new tasks)                   │
        │          │                                                       │
        │          ▼                                                       │
        │   2. If wait=True: Wait for queue to drain                      │
        │          │                                                       │
        │          ▼                                                       │
        │   3. Send poison pills to all workers                           │
        │          │                                                       │
        │          ▼                                                       │
        │   4. Wait for workers to exit                                   │
        │          │                                                       │
        │          ▼                                                       │
        │   5. Clean up                                                   │
        │                                                                  │
        └─────────────────────────────────────────────────────────────────┘
        
        Args:
            wait: Whether to wait for pending tasks to complete.
                  If False, pending tasks are abandoned.
            timeout: Maximum time to wait for shutdown.
                     If exceeded, we force-stop workers.
        """
        if not self._started:
            return
        
        logger.info("Shutting down thread pool...")
        self._shutdown = True
        
        if wait:
            # ─────────────────────────────────────────────────────────────
            # WAIT FOR QUEUE TO DRAIN
            # ─────────────────────────────────────────────────────────────
            # queue.join() blocks until all tasks are done.
            # "Done" means task_done() was called for each task.
            
            if timeout:
                deadline = time.time() + timeout
                while not self._task_queue.empty():
                    if time.time() > deadline:
                        logger.warning("Shutdown timeout, forcing stop")
                        break
                    time.sleep(0.1)
            else:
                self._task_queue.join()
        
        # ─────────────────────────────────────────────────────────────────
        # SEND POISON PILLS
        # ─────────────────────────────────────────────────────────────────
        # Put None in the queue for each worker.
        # When workers get None, they exit their loop.
        
        for _ in self._workers:
            try:
                self._task_queue.put(None, block=False)
            except queue.Full:
                pass  # Worker might already be gone
        
        # ─────────────────────────────────────────────────────────────────
        # WAIT FOR WORKERS TO EXIT
        # ─────────────────────────────────────────────────────────────────
        
        for worker in self._workers:
            worker.shutdown()
            worker.join(timeout=2.0)  # Give each worker 2s to exit
        
        self._workers.clear()
        self._started = False
        
        logger.info("Thread pool shutdown complete")
    
    # =========================================================================
    # MONITORING: Check pool status
    # =========================================================================
    
    @property
    def active_workers(self) -> int:
        """Get count of active (non-stopped) workers."""
        return sum(1 for w in self._workers if w.state != WorkerState.STOPPED)
    
    @property
    def busy_workers(self) -> int:
        """Get count of busy workers."""
        return sum(1 for w in self._workers if w.state == WorkerState.BUSY)
    
    @property
    def idle_workers(self) -> int:
        """Get count of idle workers."""
        return sum(1 for w in self._workers if w.state == WorkerState.IDLE)
    
    @property
    def queue_size(self) -> int:
        """Get current task queue size."""
        return self._task_queue.qsize()
    
    @property
    def stats(self) -> dict:
        """
        Get thread pool statistics.
        
        Returns a dict with worker and task counts,
        useful for monitoring dashboards and health checks.
        """
        total_completed = sum(w.tasks_completed for w in self._workers)
        total_failed = sum(w.tasks_failed for w in self._workers)
        
        return {
            "workers": {
                "total": len(self._workers),
                "active": self.active_workers,
                "busy": self.busy_workers,
                "idle": self.idle_workers,
            },
            "tasks": {
                "queued": self._task_queue.qsize(),
                "completed": total_completed,
                "failed": total_failed,
            },
        }
