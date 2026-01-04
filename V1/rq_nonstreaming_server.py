import random 
from rq_helper import RedisQueueManager
from datetime import datetime
from zoneinfo import ZoneInfo 
import uuid
import json
import time

Redis_Queue = RedisQueueManager()

# server_id = str( uuid.uuid4() )     # Global unique client ID
server_id = "server_" + str( random.randint(0, 10000) )    
timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
server = { "server_id": server_id, "timestamp": timestamp}

Redis_Queue.server_register(server) # Register the server

temp_no = 0 
while True:
    temp_no += 1

    task_id = Redis_Queue.dequeue_task_id() # Dequeue, FIFO
    if task_id == None:
        print("-" * 10 +f"> No {temp_no} - No task available.")
        continue

    task = Redis_Queue.load_task( task_id ) # Blocking read with automatic remove

    # Response is based on the request
    task_result = task
    task_result['status'] = "completed" if random.randint(0, 100) < 60 else "failed"
    # task_result['status'] = 'completed'
    task_result['output'] = f's3://my-bucket/my-output-file-{temp_no}.txt'
    task_result['server_id'] = server_id
    time.sleep(0.2)

    print("-" * 20 + f"> No {temp_no} - Generated task result:")
    print(json.dumps(task_result, indent=2))   
    Redis_Queue.save_task_result( task_result ) # Create a task result list with one item