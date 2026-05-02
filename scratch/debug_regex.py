import re
text = "My key is AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6 and email is test@example.com"
text = re.sub(r"AIzaSy[a-zA-Z0-9\-_]{33}", "[GOOGLE_API_KEY_MASKED]", text)
print(f"After API Key: {text}")
text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_MASKED]", text)
print(f"After Email: {text}")
