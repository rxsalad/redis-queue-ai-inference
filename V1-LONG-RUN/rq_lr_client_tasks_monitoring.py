import random
from rq_lr_helper import RedisQueueManager
from collections import deque
from pathlib import Path
import json
import time

Redis_Queue = RedisQueueManager()
TASK_ID_FILE = Path("task_ids.txt")


def monitor_all_tasks(task_id):

    code, task = Redis_Queue.monitor_lr_task(task_id) # Update task status if needed
    if code == 0:
        print("-" * 10 + f"> Task {task_id} - task done ...")
    elif code == 1:
        print("-" * 10 + f"> Task {task_id} - awaiting backend processing ...")
    elif code == 2:
        print("-" * 20 + f"> Task {task_id} - the result:")
        print(json.dumps(task, indent=2))    
        success = True if task["status"] == "completed" else False
        Redis_Queue.record( task["id"], success=success )
    else: # 3,4
        print("-" * 10 + f"> Task {task_id} - running (or interrupted and awaiting lease expiration) ...")

    return code, task
        

if __name__ == "__main__":

    # load task IDs from file 
    with TASK_ID_FILE.open("r") as f:
        task_ids = deque(line.strip() for line in f if line.strip())

    # Monitor tasks until all are completed
    while task_ids:
        time.sleep(2)  # Wait before the next check
        task_id = task_ids.popleft()  # Fast O(1) pop from the left
        code, task = monitor_all_tasks(task_id)  # Check task status
        if code != 2 and code != 0:   # Task not completed
            task_ids.append(task_id)  # Put it back at the end to retry

    print("All tasks completed!")