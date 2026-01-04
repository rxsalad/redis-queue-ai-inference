import random 
from rq_helper import RedisQueueManager
from datetime import datetime
from zoneinfo import ZoneInfo 
from rq_testdata import *
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

    print("-" * 20 + f"> No {temp_no} - Processing task:")
    print(json.dumps(task, indent=2))

    # Server: process the request
    fake_results = list_50_20
    length = len(fake_results)
    for i in range(length):
        time.sleep(0.1)   # Simulate processing time        
        fake_chunk = str(i) + "-" + fake_results[i]
        last = True if i == length - 1 else False
        Redis_Queue.save_task_result_chunk( task_id = task_id, server_id = server_id, client_id = task["client_id"], 
                                            chunk = fake_chunk, success = True, last = last )
        print(fake_chunk, flush=True)
        