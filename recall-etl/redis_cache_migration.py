
import os
import redis
import ssl

local_redis_host = os.getenv('LOCAL_REDIS_HOST', '')
local_redis_password = os.getenv('LOCAL_REDIS_PASSWORD', '')
azure_redis_host = os.getenv('AZURE_REDIS_HOST')
azure_redis_password = os.getenv('AZURE_REDIS_PASSWORD')



local_redis = redis.Redis(
        host=local_redis_host,
        port=6379,
        password=local_redis_password,
        decode_responses=True  # Return strings instead of bytes
    )

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

azure_redis = redis.Redis(
    host=azure_redis_host,
    port=6380,
    password=azure_redis_password,
    ssl=True,
    ssl_cert_reqs=None,  # This disables certificate verification
    socket_timeout=5,
    socket_connect_timeout=5
)

try:
    response = azure_redis.ping()
    print(f"Connected successfully: {response}")
except Exception as e:
    print(f"Connection failed: {type(e).__name__}: {e}")

keys = local_redis.keys('*')
print(f"Found {len(keys)} keys to migrate.")

for key in keys:
    if isinstance(key, bytes):
        key_str = key.decode('utf-8')
    else:
        key_str = key
    
    key_type_result = local_redis.type(key)
    if isinstance(key_type_result, bytes):
        key_type = key_type_result.decode('utf-8')
    else:
        key_type = key_type_result
    
    if key_type == 'string':
        value = local_redis.get(key)
        azure_redis.set(key, value)

    # Handle expiration time if needed
    ttl = local_redis.ttl(key)
    if ttl > 0:
        azure_redis.expire(key, ttl)

print("Data migration complete.")


azure_keys = azure_redis.keys('*')
print(f"Azure cache has {len(azure_keys)} keys.")






