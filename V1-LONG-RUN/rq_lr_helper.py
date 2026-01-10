import threading
from redis import Redis
from typing import Optional
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo 
from dotenv import load_dotenv
load_dotenv()

# Redis connection settings
RQ_HOST        = os.getenv("RQ_HOST", "")
RQ_PORT        = int(os.getenv("RQ_PORT", "0"))
RQ_CA_CERT     = os.getenv("RQ_CA_CERT", "")
RQ_CLIENT_CERT = os.getenv("RQ_CLIENT_CERT", "")
RQ_CLIENT_KEY  = os.getenv("RQ_CLIENT_KEY", "")

# Timeout settings for synchronous operations
WAIT_TIMEOUT    = 20  # seconds
LEASING_TIMEOUT = 60  # seconds
RENEW_INTERVAL  = 20  # seconds
RUN_TIME        = 100 # seconds

# Redis keys for task IDs only
LR_ZSET_REQUEST_PENDING    = "lr_zset_requests:pending"   # FIFO queue
LR_LIST_REQUEST_COMPLETED  = "lr_list_requests:completed" # Optional
LR_LIST_REQUEST_FAILED     = "lr_list_requests:failed"    # Optional

# Redis keys for tasks and task results (non-streaming and streaming)
LR_STRING_TASK             = "lr_string_task"


class RedisQueueManager:
    
    def __init__(self):
        # Redis connection
        self.redis = self._create_redis_connection()
        print("\n\nThe Redis Queue Manager is initialized.")
        #print(self.get_statistics())

    def _create_redis_connection(self):
        try:
            r = Redis(
                host=RQ_HOST, port=RQ_PORT, ssl=True, ssl_check_hostname=False,
                ssl_ca_certs=RQ_CA_CERT, ssl_certfile=RQ_CLIENT_CERT, ssl_keyfile=RQ_CLIENT_KEY,
                # ssl_cert_reqs=None,
                socket_connect_timeout=5,
                health_check_interval=10,
                socket_keepalive=True,
                socket_timeout=60,
                retry_on_timeout=True
            )
            return r
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            exit(1)

    def purge(self):
        try:
            print("⚠️  Be careful: This will flush the Redis queue!")
            #cmd = input("Continue? yes - flush, others - exit: ").strip().lower()
            #if cmd != "yes":
            #    os._exit(0)

            self.redis.flushdb()
            print("The Redis queue has been flushed.")
        except Exception as e:
            print(f"Error flushing database: {e}")

    def get_statistics(self) -> dict:
        return {
            'pending': self.redis.zcount(LR_ZSET_REQUEST_PENDING, '-inf', '+inf'),
            'completed': self.redis.llen(LR_LIST_REQUEST_COMPLETED),
            'failed': self.redis.llen(LR_LIST_REQUEST_FAILED)
        }
    
    def record(self, request_id: str, success=True):
        try:
            target_list = LR_LIST_REQUEST_COMPLETED if success else LR_LIST_REQUEST_FAILED
            self.redis.lpush(target_list, request_id)
        except Exception as e:
            print(f"Error recording finished request {request_id}: {e}")

    # ---------------- Queue Operations for Task IDs by Clients and Servers---------------- #

    def enqueue_lr_task_id(self, task_id: str, score: float):
        try:
            self.redis.zadd(LR_ZSET_REQUEST_PENDING, {task_id: score})
        except Exception as e:
            print(f"Error sending task {task_id}: {e}")

    def dequeue_lr_task_id(self) -> Optional[str]:
        try:
            result = self.redis.bzpopmin([LR_ZSET_REQUEST_PENDING], timeout=WAIT_TIMEOUT)
            if result is None:
                return None
            _, task_id, _ = result # (key, task_id, score)
            return task_id.decode('utf-8')
        except Exception as e:
            print("No task available or timeout.")
            return None

    # ---------------- I/O Operations for Long Run by Clients and Servers---------------- #

    def save_lr_task(self, task: dict):
        try: 
            self.redis.set(f"{LR_STRING_TASK}:{task['id']}", json.dumps(task))
        except Exception as e:
            print(f"Error saving task {task['id']}: {e}")

    def load_lr_task(self, task_id: str):
        try: 
            result = self.redis.get(f"{LR_STRING_TASK}:{task_id}")
            if result is None:
                return None
            return json.loads(result.decode('utf-8'))
        except Exception as e:
            print(f"Error loading task {task_id}: {e}")

    def delete_lr_task(self, task_id: str) -> bool:
        try:    
            self.redis.delete(f"{LR_STRING_TASK}:{task_id}")
        except Exception as e:
            print(f"Error deleting task {task_id}: {e}")
    
    def monitor_lr_task(self, task_id: str):
        try: 
            result = self.redis.get(f"{LR_STRING_TASK}:{task_id}")

            if result is None:
                return 0, {}
            task = json.loads(result.decode('utf-8'))
            if task['status'] in ['pending']:
                # May add the check for LR_ZSET_REQUEST_PENDING - the task_id is still there 
                return 1, task
            elif task['status'] in ['completed', 'failed']:
                self.delete_lr_task(task_id)
                return 2, task
            else: # running or interrupted
                duration = ( datetime.now(ZoneInfo("America/Los_Angeles")) - datetime.fromisoformat(task['update_time']) ).total_seconds() 
                if duration < LEASING_TIMEOUT: 
                    return 3, task
                else: # expired
                    task['status'] = 'pending'
                    self.save_lr_task(task)
                    self.enqueue_lr_task_id(task["id"], task["score"]) # Re-enqueue
                    print(f"Task {task_id} lease expired with {duration} seconds, re-enqueued.")
                    return 4, task

        except Exception as e:
            print(f"Error loading task {task_id}: {e}")
        
    # ---------------- Monitor ---------------- #

    def monitor(self, details = False):
        try:
            print()
            print(40 * "-" + "> Test: ping")
            print(self.redis.ping())
            
            print()
            print(40 * "-" + "> Queue Info:")
            print(self.get_statistics())

            keys = self.redis.keys("*")

            print()
            print(40 * "-" + f"> {LR_ZSET_REQUEST_PENDING}:")
            if details:
                pending_tasks = self.redis.zrange(LR_ZSET_REQUEST_PENDING, 0, -1, withscores=True)
                for task_id, score in pending_tasks:
                    print(f"----> {task_id.decode()}: {score}")

            print()
            print(40 * "-" + f"> {LR_STRING_TASK}:")
            for key in keys:
                key_str = key.decode()
                if LR_STRING_TASK == key_str.split(":")[0]:
                    print(f"----> {key_str}:")
                    if details:
                        value = self.redis.get(key_str)
                        value = json.loads(value.decode('utf-8'))
                        print(json.dumps(value, indent=2))    

            print()

        except Exception as e:
            print(f"Error retrieving Redis info: {e}")
            return {}


