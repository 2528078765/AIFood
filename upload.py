import paramiko
import os

HOST = '120.27.144.201'
USER = 'root'
PASS = 'Csy020813'
BASE = r'C:\Users\25280\Desktop\AIFood'
REMOTE_BASE = '/opt/aifood'

files = [
    'backend/app/models/user.py',
    'backend/app/api/auth.py',
    'backend/app/api/settings.py',
    'backend/app/services/api_key_service.py',
    'backend/app/schemas/settings.py',
    'backend/app/agent/agent.py',
    'database/migration_add_trial.sql',
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS)
sftp = ssh.open_sftp()

for f in files:
    local = os.path.join(BASE, f)
    remote = REMOTE_BASE + '/' + f
    print(f'Uploading {f}...')
    sftp.put(local, remote)
    print(f'  OK')

sftp.close()

print('\nRunning DB migration...')
stdin, stdout, stderr = ssh.exec_command(
    'cd /opt/aifood && docker compose exec -T postgres psql -U postgres -d aifood -c "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP WITH TIME ZONE;"'
)
out = stdout.read().decode()
err = stderr.read().decode()
if out:
    print(out)
if err:
    print(err)

print('\nRebuilding Docker app container...')
stdin, stdout, stderr = ssh.exec_command('cd /opt/aifood && docker compose up -d --build app 2>&1')
for line in iter(stdout.readline, ''):
    print(line, end='')

ssh.close()
print('\nDone!')
