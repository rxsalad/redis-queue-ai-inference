from redis import Redis
from typing import Optional
import json
import os
import time
from dotenv import load_dotenv
load_dotenv()

# Redis connection settings
RQ_HOST        = os.getenv("RQ_HOST", "")
RQ_PORT        = int(os.getenv("RQ_PORT", "0"))
RQ_CA_CERT     = os.getenv("RQ_CA_CERT", "")
RQ_CLIENT_CERT = os.getenv("RQ_CLIENT_CERT", "")
RQ_CLIENT_KEY  = os.getenv("RQ_CLIENT_KEY", "")

# Timeout settings for synchronous operations
WAIT_TIMEOUT   = 20  # seconds

# Redis keys for clients and servers
LIST_CLIENTS            = "list_clients"
LIST_SERVERS            = "list_servers"

# Redis keys for task IDs only
ZSET_REQUEST_PENDING    = "zset_requests:pending"   # FIFO queue
LIST_REQUEST_COMPLETED  = "list_requests:completed" # Optional
LIST_REQUEST_FAILED     = "list_requests:failed"    # Optional

# Redis keys for tasks and task results (non-streaming and streaming)
LIST_TASK                   = "list_task"
LIST_TASK_RESULT            = "list_task_result"
LIST_TASK_RESULT_STREAMING  = "list_task_result_streaming"


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
                #ssl_cert_reqs=None,
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
            cmd = input("Continue? yes - flush, others - exit: ").strip().lower()
            if cmd != "yes":
                os._exit(0)

            self.redis.flushdb()
            print("The Redis queue has been flushed.")
        except Exception as e:
            print(f"Error flushing database: {e}")

    def get_statistics(self) -> dict:
        return {
            'pending': self.redis.zcount(ZSET_REQUEST_PENDING, '-inf', '+inf'),
            'completed': self.redis.llen(LIST_REQUEST_COMPLETED),
            'failed': self.redis.llen(LIST_REQUEST_FAILED)
        }
    
    def record(self, request_id: str, success=True):
        try:
            target_list = LIST_REQUEST_COMPLETED if success else LIST_REQUEST_FAILED
            self.redis.lpush(target_list, request_id)
        except Exception as e:
            print(f"Error recording finished request {request_id}: {e}")

    def client_register(self, client: dict):
        try:
            self.redis.lpush(LIST_CLIENTS, json.dumps(client))
            print(f"Client registered - {client}.")
        except Exception as e:
            print(f"Error registering client {client}: {e}")

    def server_register(self, server: dict):
        try:
            self.redis.lpush(LIST_SERVERS, json.dumps(server))
            print(f"Server registered - {server}.") 
        except Exception as e:
            print(f"Error registering server {server}: {e}")

    # ---------------- Queue Operations for Task IDs by Clients and Servers---------------- #

    def enqueue_task_id(self, task_id: str):
        try:
            self.redis.zadd(ZSET_REQUEST_PENDING, {task_id: time.time()})
        except Exception as e:
            print(f"Error sending task {task_id}: {e}")

    def dequeue_task_id(self) -> Optional[str]:
        try:
            result = self.redis.bzpopmin([ZSET_REQUEST_PENDING], timeout=WAIT_TIMEOUT)
            if result is None:
                return None
            _, task_id, _ = result
            return task_id.decode('utf-8')
        except Exception as e:
            print("No task available or timeout.")
            return None
        
    # ---------------- I/O Operations for Tasks and Results by Clients and Servers---------------- #
    
    def save_task(self, task: dict):
        try: # Add the only item to the list (left), which represents a specific task
            self.redis.lpush(f"{LIST_TASK}:{task['id']}", json.dumps(task))
        except Exception as e:
            print(f"Error saving task {task['id']}: {e}")

    def load_task(self, task_id: str):
        try: # Block and remove the item from the list (right)
            result = self.redis.brpop(f"{LIST_TASK}:{task_id}", timeout=WAIT_TIMEOUT)
            if result is None:
                return None
            _, data = result
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error loading task {task_id}: {e}")

    def save_task_result(self, task: dict):
        try: # Add the only item to the list (left), which represents a specific task result
            self.redis.lpush(f"{LIST_TASK_RESULT}:{task['id']}", json.dumps(task))
        except Exception as e:
            print(f"Error saving task {task['id']}: {e}")

    def load_task_result(self, task_id: str):
        try: # block and remove the item from the list (right)
            result = self.redis.brpop(f"{LIST_TASK_RESULT}:{task_id}", timeout=WAIT_TIMEOUT)
            if result is None:
                return None
            _, data = result
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error loading task {task_id}: {e}")

    def save_task_result_chunk(self, task_id: str, server_id: str, client_id: str, chunk: str, success: bool, last: bool):
        try: # Add an item to the list (left), which represents a specific task
            data = json.dumps({ "id": task_id,
                                "server_id": server_id,
                                "client_id": client_id,
                                "chunk": chunk,  
                                "success": success,
                                "last": last })
            self.redis.lpush(f"{LIST_TASK_RESULT_STREAMING}:{task_id}", data)
        except Exception as e:
            print(f"Error saving chunk for task {task_id}: {e}")

    def load_task_result_chunk(self, task_id: str) -> Optional[dict]:
        try: # Block and remove the item from the list (right)
            result = self.redis.brpop([f"{LIST_TASK_RESULT_STREAMING}:{task_id}"], timeout=WAIT_TIMEOUT)
            if result is None:
                return None
            _, data = result
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Error loading chunk for task {task_id}: {e}")
            return None
        
    # ---------------- Monitor ---------------- #

    def monitor(self, details = False):
        try:
            print()
            print(40 * "-" + "> Test: ping")
            print(self.redis.ping())
            
            print()
            print(40 * "-" + "> Queue Info:")
            print(self.get_statistics())

            print()
            print(40 * "-" + "> Clients and Servers:")
            print(10 * "-" + "> Clients:")
            clients = self.redis.lrange(LIST_CLIENTS, 0, -1)
            for temp in clients:
                print(temp)
            print(10 * "-" + "> Servers:")    
            servers = self.redis.lrange(LIST_SERVERS, 0, -1)
            for temp in servers:
                print(temp)
      
            keys = self.redis.keys("*")
            
            print()
            print(40 * "-" + f"> {LIST_TASK}:")
            for key in keys:
                key_str = key.decode()
                if LIST_TASK == key_str.split(":")[0]:
                    print(f"----> {key_str}:")
                    if details:
                        chunks = self.redis.lrange(key, 0, -1)
                        for chunk in chunks:
                            print(chunk)

            print()
            print(40 * "-" + f"> {LIST_TASK_RESULT}:")
            for key in keys:
                key_str = key.decode()
                if LIST_TASK_RESULT == key_str.split(":")[0]:
                    print(f"----> {key_str}:")
                    if details:
                        chunks = self.redis.lrange(key, 0, -1)
                        for chunk in chunks:
                            print(chunk)

            print()
            print(40 * "-" + f"> {LIST_TASK_RESULT_STREAMING}:")
            for key in keys:
                key_str = key.decode()
                if LIST_TASK_RESULT_STREAMING == key_str.split(":")[0]:
                    print(f"----> {key_str}:")
                    if details:
                        chunks = self.redis.lrange(key, 0, -1)
                        for chunk in chunks:
                            print(chunk)
            print()

        except Exception as e:
            print(f"Error retrieving Redis info: {e}")
            return {}