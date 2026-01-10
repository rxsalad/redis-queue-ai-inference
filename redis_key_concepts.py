import os
from redis import Redis
import json
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
                                 #ssl_cert_reqs=None,
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




# The frontend application 
# Create a sample request
c_request_001 = { "input": "s3://my_bucket/my_input_file.txt", "output": "" }

# Save the request in a list with 1 element - Key: "request_001", Value: [ { "input": "s3://my_bucket/my_input_file.txt", "output": "" } ]
rs_frontend_application.lpush("request_001", json.dumps( c_request_001 ))
rs_frontend_application.expire("request_001", 3600)     # The list is deleted when the TTL expires.

# Enqueue the key - "request_001" to the zset - "request_id_queue"
rs_frontend_application.zadd("request_id_queue", {"request_001": 1})
rs_frontend_application.expire("request_id_queue", 300) # Refresh the TTL when enqueuing a new request_id (The entire ZSET will be deleted once the TTL expires)

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




s_status = "completed"
rs_backend_server.set("task_state_001", s_status) # Save the task status

temp = rs_frontend_application.get("task_state_001") # Load the task status
if temp is not None:
    c_status = temp.decode('utf-8') 
    print(c_status)

rs_frontend_application.delete("task_state_001") # Delete the task status
    