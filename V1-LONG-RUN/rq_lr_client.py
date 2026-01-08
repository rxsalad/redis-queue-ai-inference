import random
from rq_lr_helper import RedisQueueManager
from datetime import datetime
from zoneinfo import ZoneInfo 
import uuid
import time
from collections import deque
from pathlib import Path

Redis_Queue = RedisQueueManager()
TASK_ID_FILE = Path("task_ids.txt")

# client_id = str( uuid.uuid4() )     # Global unique client ID
client_id = "client_" + str( random.randint(0, 10000) )     
timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
client = { "client_id": client_id, "timestamp": timestamp }


if __name__ == "__main__":

    task_ids = deque([])
    for temp_no in range(1,6):    

        global_task_id = str( uuid.uuid4() ) + "_" + str(temp_no) # Global unique task ID 
        timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
    
        task = { "id":            global_task_id,   # Global unique task ID, for both request and response.   
                 "score":         time.time(),
                 "client_id":      {**client, "req_id": temp_no},
                 "timestamp":     timestamp, 
                 "update_time":   timestamp,
                 "input":         f"s3://my-bucket/my-input-file-{temp_no}.txt",
                 "status":        "pending", # pending, running, completed, failed
                 "output":        "",
                 "renew_num":     0,
                 "server_id":     []
        }

        Redis_Queue.save_lr_task(task) 
        Redis_Queue.enqueue_lr_task_id(task["id"], task["score"]) # Enqueue, FIFO
        task_ids.append( task["id"] ) # Keep track of task IDs for monitoring

    # Save task IDs to a file for reference
    with TASK_ID_FILE.open("w") as f:
        for task_id in task_ids:
            f.write(f"{task_id}\n")