# Programming Access in Redis

[Redis](https://github.com/redis/redis) executes commands on a single thread, providing simplicity, atomicity, low latency, and predictable performance by eliminating locks and contention. High concurrency is achieved through non-blocking I/O and an event-driven architecture that efficiently handles thousands of client connections without being blocked by slow network operations.

The [Python Redis client](https://github.com/redis/redis-py) uses a connection pool to manage connections efficiently, reducing overhead. Instead of establishing a new connection for each request, it initializes the connection lazily on the first command and reuses it for subsequent requests. 

To begin programming access, first generate TLS certificates and private keys for both the Redis server and its clients—including both **frontend applications** and **backend servers**-then configure the Redis server to use mTLS, as outlined in [this guide](README-REDIS.md).

**Clients (frontend applications)** <-- mTLS --> **Redis server** <-- mTLS --> **Clients (backend servers)**

Next, copy the Redis client’s certificate and private key files into the designated directory, which will be used by both frontend and backend components:

``` shell
ls  -ls

4 -rw-r--r-- 1 root root 1805 Jan  2 02:20 ca.crt
4 -rw-r--r-- 1 root root 1342 Jan  2 02:20 redis-client.crt
4 -rw-r--r-- 1 root root 1704 Jan  2 02:20 redis-client.key
```

Create a [.env](.env) file in the workspace root to centrally manage access credentials:

``` shell
RQ_HOST=rq.rshue.com # Redis server used in this test
RQ_PORT=6379

# In this example, the certificate (.crt) and key (.key) files are located in the folder /root/data/redis-queue-ai-inference/redis-config/
RQ_CA_CERT=/root/data/redis-queue-ai-inference/redis-config/ca.crt
RQ_CLIENT_CERT=/root/data/redis-queue-ai-inference/redis-config/redis-client.crt 
RQ_CLIENT_KEY=/root/data/redis-queue-ai-inference/redis-config/redis-client.key
```

Here are some basic code operations:

``` python
import os
from redis import Redis
from dotenv import load_dotenv
load_dotenv()

RQ_HOST        = os.getenv("RQ_HOST", "")
RQ_PORT        = int(os.getenv("RQ_PORT", "0"))
RQ_CA_CERT     = os.getenv("RQ_CA_CERT", "")
RQ_CLIENT_CERT = os.getenv("RQ_CLIENT_CERT", "")
RQ_CLIENT_KEY  = os.getenv("RQ_CLIENT_KEY", "")

rs_frontend_application = Redis( host=RQ_HOST, 
                                 port=RQ_PORT, 
                                 ssl=True, 
                                 ssl_check_hostname=False,
                                 ssl_ca_certs=RQ_CA_CERT, 
                                 ssl_certfile=RQ_CLIENT_CERT, 
                                 ssl_keyfile=RQ_CLIENT_KEY,
                                 socket_connect_timeout=5,
                                 health_check_interval=10,
                                 socket_keepalive=True,
                                 socket_timeout=60)

# In practice, multiple frontend applications and backend servers run in different environments, here just for demonstration.
rs_backend_server = rs_frontend_application 

all_keys = rs_frontend_application.keys("*")                # Get all keys in the Redis database

for key in all_keys:                                        # Iterate through keys and print their types
    key_type = rs_backend_server.type(key).decode('utf-8')  # Redis returns bytes, decode to string
    print(f"{key.decode('utf-8')}: {key_type}")
```

Redis stores data as key-value pairs, where each key is unique and maps to a value that can be a string, list, hash, sorted set (zset), or other data structures. Let’s explore some of these data types and see how they can be used to build a queue. Please refer to [the code](redis_key_concepts.py) for complete examples.

## Data Type: ZSET

A zset (sorted set) in Redis is a data structure that holds unique elements, each associated with a score. Elements are automatically stored in order of their scores, allowing efficient retrieval by rank. We can quickly access or remove the element with the highest or lowest score. The ranking mechanism is especially useful when re-queuing a failed request, enabling it to be processed first.

The below example code demonstrates frontend applications sending 3 requests with different scores to a zset, which backend servers then retrieve in order from lowest to highest:

``` python
# In practice, multiple frontend applications send requests concurrently
rs_frontend_application1 = rs_frontend_application2 = rs_frontend_application3 = rs_frontend_application

rs_frontend_application1.zadd("request_id_queue", {"request_003": 3})
rs_frontend_application2.zadd("request_id_queue", {"request_002": 2})
rs_frontend_application3.zadd("request_id_queue", {"request_001": 1})

# In practice, multiple backend servers receive requests concurrently
rs_backend_server1 = rs_backend_server2 = rs_backend_server3 = rs_backend_server

result =rs_backend_server1.bzpopmin(["request_id_queue"], timeout=10)
if result is not None:
    _, request_id, _ = result # (key, request_id, score)
    print(request_id.decode('utf-8'))

result =rs_backend_server2.bzpopmin(["request_id_queue"], timeout=10)
if result is not None:
    _, request_id, _ = result # (key, request_id, score)
    print(request_id.decode('utf-8'))

result =rs_backend_server3.bzpopmin(["request_id_queue"], timeout=10)
if result is not None:
    _, request_id, _ = result # (key, request_id, score)
    print(request_id.decode('utf-8'))
```

Even under concurrent access from multiple frontend applications and backend servers, the Redis server executes all commands serially, ensuring atomicity and predictable results—so `“first come, first served”` holds true from the Redis server’s perspective.

## Data Type: LIST

A list in Redis is an ordered collection of elements, where items are stored in the order they are inserted. It supports efficient insertion and removal from both ends and is automatically removed when it becomes empty. Lists also support blocking operations, allowing clients to wait for elements with a specified timeout. These features make lists well suited for transferring requests and responses between frontend and backend components. By inserting and removing elements at opposite ends of a list, the frontend and backend can also implement a streaming pattern, such as streaming tokens in large language models (LLMs).

The below example code illustrates how the frontend application sents a request to the backend server using the zset and a list. 

``` python 
# The frontend application 

# Create a sample request
c_request_001 = { "input": "s3://my_bucket/my_input_file.txt", "output": "" }

# Save the request in a list with 1 element - Key: "request_001", Value: [ { "input": "s3://my_bucket/my_input_file.txt", "output": "" } ]
rs_frontend_application.lpush("request_001", json.dumps(c_request_001))
rs_frontend_application.expire("request_001", 3600)     # The list is deleted when the TTL expires.

# Enqueue the key - "request_001" to the zset - "request_id_queue"
rs_frontend_application.zadd("request_id_queue", {"request_001": 1})
rs_frontend_application.expire("request_id_queue", 300) # Refresh the TTL when enqueuing a new request_id (The entire ZSET will be deleted once the TTL expires)
```

``` python
# The backend server

# Dequeue the key - "request_001" from the zset - "request_id_queue"
rs_backend_server.expire("request_id_queue", 300) # Refresh the TTL when dequeuing a request_id (The entire ZSET will be deleted once the TTL expires)
temp = rs_backend_server.bzpopmin(["request_id_queue"], timeout=10)
if temp is not None:
    _, request_id, _ = temp # (key, request_id, score)
    request_id = request_id.decode('utf-8')
    print(request_id)       # request_id == "request_001" 

# Load the request from the list with key "request_001" (the list is automatically removed once its last element is popped)
temp = rs_backend_server.brpop(f"{request_id}", timeout=10)
if temp is not None:
    _, s_request_001 = temp
    s_request_001 = json.loads(s_request_001.decode('utf-8'))
    print(s_request_001)
```

The request ID ("request_001") and the request payload are stored using different Redis data types—an element in the zset and a single-element list—because they serve different roles and have distinct lifecycles. If a backend server fails to process a request, the frontend application can safely re-queue the corresponding request_id for retry without duplicating the request payload.

**In Redis, TTL applies per key, not per element.** In this example, the zset’s TTL (60 seconds) is refreshed whenever a request ID is enqueued or dequeued. This ensures that all request IDs are automatically expired and cleaned up if the queue becomes inactive.

The request list also has a TTL of 3600 seconds, longer than that of the request ID, ensuring the requests remains available while their corresponding ID are still active.

## Data Type: STRING

A string in Redis is a simple key-value pair where the value can be text, numbers, or binary data. Keys can be automatically removed when deleted or when their TTL expires.

The example code below illustrates how the frontend and backend components exchange a task status using a string.

``` python
s_status = "completed"
rs_backend_server.set("task_state_001", s_status)    # Save the task status

temp = rs_frontend_application.get("task_state_001") # Load the task status
if temp is not None:
    c_status = temp.decode('utf-8') 
    print(c_status)

rs_frontend_application.delete("task_state_001")     # Delete the task status
```
