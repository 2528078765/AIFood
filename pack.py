"""一键打包脚本 —— 把 backend/ 打包成 backend.zip，上传到微信云托管即可部署"""

import zipfile
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
OUTPUT = os.path.join(ROOT, "backend.zip")

def pack():
    files_to_pack = [
        "Dockerfile",
        "requirements.txt",
        "alembic.ini",
    ]

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files_to_pack:
            path = os.path.join(BACKEND, f)
            if os.path.exists(path):
                z.write(path, arcname=f)

        for folder in ["app", "alembic", "scripts"]:
            folder_path = os.path.join(BACKEND, folder)
            if not os.path.exists(folder_path):
                continue
            for root, dirs, filenames in os.walk(folder_path):
                for f in filenames:
                    if f.endswith(".pyc") or "__pycache__" in root:
                        continue
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, BACKEND).replace("\\", "/")
                    z.write(full, arcname=arc)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"[OK] {OUTPUT} ({size_kb:.1f} KB)")
    print("[Next] 去微信云托管 -> aifood 服务 -> 发布 -> 上传 backend.zip")

if __name__ == "__main__":
    pack()
