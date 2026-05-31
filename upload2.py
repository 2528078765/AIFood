#!/usr/bin/env python3
"""Upload backend files to server and rebuild Docker."""
import subprocess
import sys

HOST = "root@120.27.144.201"
BASE = r"C:\Users\25280\Desktop\AIFood"
REMOTE = "/opt/aifood"

files = [
    r"backend\app\models\user.py",
    r"backend\app\api\auth.py",
    r"backend\app\api\settings.py",
    r"backend\app\services\api_key_service.py",
    r"backend\app\schemas\settings.py",
    r"backend\app\agent\agent.py",
    r"database\migration_add_trial.sql",
]

# Step 1: Upload files one by one
for f in files:
    local = f"{BASE}\\{f}"
    remote = f"{REMOTE}/{f.replace(chr(92), '/')}"
    print(f"Uploading {f} ...")
    cmd = ["scp", local, f"{HOST}:{remote}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr}")
    else:
        print("  OK")

# Step 2: Run DB migration and rebuild
print("\nRunning DB migration and rebuild on server...")
ssh_cmd = [
    "ssh", HOST,
    "cd /opt/aifood && "
    'docker compose exec -T postgres psql -U postgres -d aifood -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP WITH TIME ZONE;" && '
    "docker compose up -d --build app"
]
result = subprocess.run(ssh_cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)

print("\nAll done!")
