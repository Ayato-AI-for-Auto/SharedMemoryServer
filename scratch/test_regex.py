import re

output = "  TCP         127.0.0.1:8377         0.0.0.0:0              LISTENING       5300"
port = 8377
pattern = re.compile(rf":{port}\s+.*\s+LISTENING\s+(\d+)")
match = pattern.search(output)
if match:
    print(f"Matched! PID: {match.group(1)}")
else:
    print("No match.")
