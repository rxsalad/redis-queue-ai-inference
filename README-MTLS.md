# mTLS Authentication

To enable mutual TLS (mTLS) authentication for Redis, we first create a private Certificate Authority (CA) that serves as the trust anchor, which is then used to issue certificates for both the Redis server and its clients. A self-signed root CA certificate and private key are generated to sign and validate all Redis-related certificates.

Next, a server private key and Certificate Signing Request (CSR) are generated for the Redis server and signed by the CA, producing a server certificate trusted by any client that has the CA certificate. The server private key’s ownership and permissions are carefully set to allow access by the redis group while preventing unauthorized reads.

Finally, a client private key and CSR are created and signed by the same CA, enabling Redis clients to authenticate themselves to the server.

Together, these steps establish encrypted communication and robust, bidirectional authentication between the Redis server and its clients—including frontend applications and backend services—using certificates issued by a trusted internal CA.

**Redis clients (frontend applications) <- mTLS -> Redis server <- mTLS -> Redis clients (backend services)**

## Generate a Certificate Authority (the root CA)

``` shell
# Generate CA private key
openssl genrsa -out ca.key 4096

# Generate CA certificate (self-signed, 10 years)
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt -subj "/CN=Redis-CA"
```

## Generate Redis Server Certificate

``` shell
# Server private key
openssl genrsa -out redis-server.key 2048

# Server CSR (Certificate Signing Request)
openssl req -new -key redis-server.key -out redis-server.csr -subj "/CN=redis-server"

# Sign server certificate with the root CA
openssl x509 -req -in redis-server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis-server.crt -days 3650 -sha256

# Grant the Redis user access to the key, since most Linux installations run the Redis server under this account.
chown root:redis redis-server.key
chmod 640 redis-server.key

# Before:
  4 -rw------- 1 root root    1704 Jan  2 01:20 redis-server.key
# After:
  4 -rw-r----- 1 root redis   1704 Jan  2 01:20 redis-server.key
```

## Generate Client Certificate

``` shell
# Client private key
openssl genrsa -out redis-client.key 2048

# Client CSR (Certificate Signing Request)
openssl req -new -key redis-client.key -out redis-client.csr -subj "/CN=redis-client"

# Sign client certificate with the root CA
openssl x509 -req -in redis-client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis-client.crt -days 3650 -sha256
```

## Final Files and Their Distribution

The CA does not require its private key (ca.key) at runtime; it is only needed to sign server and client certificates during setup. 

At runtime, both the Redis server and clients must retain their own private keys to prove `ownership` of their respective certificates during [the TLS handshake](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/). This allows each party to authenticate itself and establish a secure, encrypted connection, while the CA’s public certificate (ca.crt) is used by both sides to verify the authenticity of the presented certificates.

``` shell
# The most sensitive file, and it must be kept secure
ca.key

# Root CA certificate shared by Redis server and clients to verify the authenticity of server and client  certificates
ca.crt

# For Redis server 
redis-server.crt
redis-server.key

# For Redis clients 
redis-client.crt
redis-client.key
```