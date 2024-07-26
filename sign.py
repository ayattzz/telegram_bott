
import hmac
import hashlib
import json

SECRET_KEY = "+GAtFHo4O763z0DJL5e0055rjFOLMEo9"  # Ensure this matches the key used in FastAPI

# Example payload (should match what NOWPayments sends)
payload = {"order_id":"1695689621","payment_status":"finished"}

# Convert payload to a JSON string with sorted keys
payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
print(f"Payload: {payload_str}")

# Compute the HMAC SHA-512 signature
signature = hmac.new(bytes(SECRET_KEY, 'utf-8'), payload_str.encode('utf-8'), hashlib.sha512).hexdigest()
print(f"Computed Signature: {signature}")
