import random
from rq_helper import RedisQueueManager
from datetime import datetime
from zoneinfo import ZoneInfo 
import uuid
import json

Redis_Queue = RedisQueueManager()

# client_id = str( uuid.uuid4() )     # Global unique client ID
client_id = "client_" + str( random.randint(0, 10000) )     
timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
client = { "client_id": client_id, "timestamp": timestamp }

Redis_Queue.client_register(client) # Register the client

for temp_no in range(1,6):    

    global_task_id = str( uuid.uuid4() ) + "_" + str(temp_no) # Global unique task ID 
    timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
    
    task = { "id":         global_task_id,   # Global unique task ID, for both request and response.   
             "client_id":  client_id, 
             "timestamp":  timestamp, 
             "input":      f"s3://my-bucket/my-input-file-{temp_no}.txt",
             "status":     "pending", # pending, completed, failed
             "output":     "",
             'server_id':  ""
    }

    Redis_Queue.save_task( task ) # Create a task list with one item 
    Redis_Queue.enqueue_task_id( task_id = task["id"] ) # Enqueue, FIFO

    # Do other things before waiting for response

    print("-" * 20 + f"> No {temp_no} - The result of the test:")
    print(json.dumps(task, indent=2))
    
    while True:
        chunk_data = Redis_Queue.load_task_result_chunk( task["id"] )
        if chunk_data != None:
           print(chunk_data, flush=True)
           if chunk_data['last'] == False: 
               continue
           else:
               success = chunk_data['success'] # True if last chunk indicates success
               break
        else: # Timeout
            print("-" * 10 +f"> No {temp_no} - Timeout waiting for task result.")
            success = False
            break

    Redis_Queue.record( task["id"], success=success )







