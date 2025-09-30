import threading, time
from collections import deque
from typing import Dict, Any
from graph.ops_graph import run_task as _run_task
from vme_lib import supabase_client as _sbmod
import routes.ops as _ops_module

_queue = deque()
_lock = threading.Lock()
_worker_thread = None
_stop = False


def enqueue_task(task: Dict[str, Any]):
    with _lock:
        _queue.append(task)
    _ensure_worker()


def _ensure_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def _emit_event(task_id: int, kind: str, data: Dict[str, Any]):
    # persist
    try:
        _sbmod._client()
    except Exception:
        pass
    try:
        _sbmod.insert_task_event(task_id=task_id, kind=kind, data_dict=data)
    except Exception:
        pass
    # also append to in-proc buffer so SSE subscribers get it
    try:
        _ops_module._append_event(task_id, kind, data)
    except Exception:
        pass


def _worker_loop():
    global _stop
    while not _stop:
        task = None
        with _lock:
            if _queue:
                task = _queue.popleft()
        if not task:
            time.sleep(0.2)
            continue
        tid = int(task.get('id'))
        try:
            # mark running
            try:
                _sbmod.update_task_status(tid, 'running')
            except Exception:
                pass
            # run the task via ops_graph
            def emit(kind, data):
                _emit_event(tid, kind, data)
            ok = _run_task(title=task.get('title'), body=task.get('body'), emit=emit)
            # set final status
            try:
                _sbmod.update_task_status(tid, 'success' if ok else 'failed')
            except Exception:
                pass
        except Exception as e:
            try:
                _sbmod.update_task_status(tid, 'failed', error=str(e))
            except Exception:
                pass


def stop_worker():
    global _stop
    _stop = True


def start_worker():
    _ensure_worker()
