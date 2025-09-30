import os, time

# Minimal ops graph: deterministic fake that emits ticks then done when DEV_LOCAL_LLM=1

def run_task(title: str | None, body: str | None, emit):
    """Run a task. emit(kind,data) is called for events. Return True on success."""
    if os.getenv('DEV_LOCAL_LLM','').lower() in ('1','true','yes') or not os.getenv('OPENAI_API_KEY'):
        try:
            for i in range(4):
                emit('tick', {'seq': i+1, 'msg': f'tick {i+1}'})
                time.sleep(0.12)
            emit('done', {'msg': 'done'})
            return True
        except Exception:
            try:
                emit('error', {'msg': 'exception'})
            except Exception:
                pass
            return False
    # Production stub: would build agent with tools and run plan
    try:
        emit('log', {'msg': 'starting real run (no-op in this stub)'})
        time.sleep(0.2)
        emit('done', {'msg': 'done'})
        return True
    except Exception:
        emit('error', {'msg': 'failed'})
        return False
