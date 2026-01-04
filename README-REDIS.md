# Enable mTLS Authentication for Redis

Follow [this guide](https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-redis-on-ubuntu-22-04) to install the Redis server.

``` shell
apt update
apt install net-tools
apt install redis-server
```

Create TLS certificates and private keys for both the Redis server and clients according to [this guide](README-MTLS.md).

``` shell
# For Redis server 
ca.crt
redis-server.crt
redis-server.key

# For Redis clients 
ca.crt
redis-client.crt
redis-client.key
```

Copy the Redis server’s TLS certificate and private key files to the target directory:

``` shell
cp ca.crt redis-server.crt redis-server.key /etc/redis

# Verify file permissions and ownership
ls /etc/redis -ls
total 120
  4 -rw-r--r-- 1 root  redis   1805 Jan  2 01:33 ca.crt
  4 -rw-r--r-- 1 root  redis   1342 Jan  2 01:33 redis-server.crt
  4 -rw-r----- 1 root  redis   1704 Jan  2 01:33 redis-server.key
108 -rw-r----- 1 redis redis 106604 Oct 13 15:22 redis.conf
```

Modify the Redis configuration file ([before](redis/redis_old.conf) vs. [after](redis/redis_new.conf)):

``` shell
nano /etc/redis/redis.conf

supervised systemd
bind 127.0.0.1 -::1 -> bind * # Allows Redis to accept connections on all network interfaces

port 6379 -> port 0 # Disables unencrypted TCP
tls-port 6379       # Enables TLS-only connections on port 6379   

tls-cert-file /etc/redis/redis-server.crt
tls-key-file /etc/redis/redis-server.key
tls-ca-cert-file /etc/redis/ca.crt
tls-auth-clients yes

protected-mode yes -> protected-mode no # Safe to disable because mTLS is enabled

maxclients 10000 # Limits maximum simultaneous client connections
``` 

Restart the Redis service to reflect the changes made to the configuration file:

``` shell
systemctl restart redis.service
systemctl status redis
``` 

Test the Redis with mTLS using the client'scertificate and private key:

``` shell
redis-cli --tls \
  -h rq.rshue.com \
  -p 6379 \
  --cacert ca.crt \
  --cert redis-client.crt \
  --key redis-client.key \
  PING

PONG
``` 

A TCP connection can be established without completing a TLS handshake; however, when Redis is configured for TLS-only access, the server immediately closes any connection that does not perform a valid TLS handshake. To prevent potential abuse, setting a limit on the maximum number of client connections helps protect against connection exhaustion attacks.

``` shell
redis-cli \
  -h rq.rshue.com \
  -p 6379 

rq.rshue.com:6379> 
rq.rshue.com:6379> keys *
Error: Connection reset by peer
not connected> 
not connected> 
``` 

Below are some example commoands for Reids: 

``` shell
redis-cli --tls \
  -h rq.rshue.com \
  -p 6379 \
  --cacert ca.crt \
  --cert redis-client.crt \
  --key redis-client.key 

rq.rshue.com:6379> flushdb # Deletes all keys in the currently selected Redis database
rq.rshue.com:6379> 
rq.rshue.com:6379> keys *  # Returns a list of all keys in the current database
rq.rshue.com:6379> 
rq.rshue.com:6379> lrange list_servers 0 -1 # Retrieve all elements from the list
rq.rshue.com:6379> 
rq.rshue.com:6379> zrange zset_requests:pending 0 -1 # Retrieve all elements from the sorted set
rq.rshue.com:6379>
rq.rshue.com:6379> type list_clients # Returns the data type
rq.rshue.com:6379>
rq.rshue.com:6379> exit
``` shell