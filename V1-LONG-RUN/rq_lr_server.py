import random 
from rq_lr_helper import RedisQueueManager, RENEW_INTERVAL, RUN_TIME
from datetime import datetime
from zoneinfo import ZoneInfo 
import uuid
import json
import time
import threading
 
Redis_Queue = RedisQueueManager()

# server_id = str( uuid.uuid4() )     # Global unique client ID
server_id = "server_" + str( random.randint(0, 10000) )    
timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
server = { "server_id": server_id, "timestamp": timestamp }


def lease_renew_worker(stop_event: threading.Event, task: dict):

    worker_name = str(random.randint(0, 10000))

    print("-" * 10 + f"> The lease renew worker {worker_name} just started", flush=True)
    n = 0

    while not stop_event.is_set(): # running untile stop_event is set
    
        timestamp = str( datetime.now(ZoneInfo("America/Los_Angeles")) )
        task['update_time'] = timestamp
        task['renew_num'] += 1
        Redis_Queue.save_lr_task(task)

        print("-" * 10 + f"> No {n} lease renewing ...", flush=True)
        n = n + 1

        if stop_event.wait(timeout=RENEW_INTERVAL): # True if stop_event is set; False if timeout
            break

    print("-" * 10 + f"> The lease renew worker {worker_name} stopped gracefully", flush=True)


def main():

    temp_no = 0
    while True:
        temp_no += 1

        ######################################## 
        task_id = Redis_Queue.dequeue_lr_task_id() # Dequeue, FIFO
        if task_id == None:
            print("-" * 10 +f"> No {temp_no} - No task available.")
            continue

        # If interrupted here (low possibility), the task will be lost
        # May add a check in the tasks monitoring for production
    
        task = Redis_Queue.load_lr_task(task_id)  
        if task == None:
            print("-" * 10 +f"> No {temp_no} - Task {task_id} not found.")
            continue
        task['status'] = "running"
        task['server_id'].append( {**server, 'renew_start': task['renew_num']} )
        
        print("-" * 20 + f"> No {temp_no} - Retrieved a new task:")
        print(json.dumps(task, indent=2))   
        ########################################

        ######################################## 
        stop_event = threading.Event() # The shared signal between the main thread and the child thread, initially False
        #t = threading.Thread(target=lease_renew_worker, args=(stop_event, task), daemon=True)
        t = threading.Thread(target=lease_renew_worker, args=(stop_event, task))
        t.start()
        time.sleep(2)

        # Do the long run work here, and should not modify the 'task' until done (avoid the race condition with the lease renew worker) 
        # Could be interrupted during long run 
        try:
            for i in range(RUN_TIME): 
                print(f"Main thread working... {i}", flush=True)
                time.sleep(1)
        except KeyboardInterrupt: # Simulate the interruption
            print("The main thread is interrupted.")
            print("Signaling the child thread to stop", flush=True)
            stop_event.set() # Tell the child thread to stop
            t.join()         # Waits until worker thread exits cleanly 
            exit(-1)     

        # In practice, the lease renew worker thread may still be running for a while

        print("Signaling the child thread to stop", flush=True)
        stop_event.set() # Tell the child thread to stop
        t.join()         # Waits until worker thread exits cleanly 
        ########################################

        # task['status'] = "completed" if random.randint(0, 100) < 80 else "failed"
        task['status'] = "completed"
        task['output'] = f's3://my-bucket/my-output-file-{temp_no}.txt'

        print("-" * 20 + f"> No {temp_no} - Generated task result:")
        print(json.dumps(task, indent=2))   

        Redis_Queue.save_lr_task(task) 


if __name__ == "__main__":
    main()







    




