# check_dirs.py
from app import create_app
import os

app = create_app()

print("=" * 60)
print("📂 目录配置检查")
print("=" * 60)
print(f"BASE_DIR:    {app.config.get('BASE_DIR', 'Not set')}")
print(f"DB_DIR:      {app.config['DB_DIR']}")
print(f"UPLOAD_DIR:  {app.config['UPLOAD_DIR']}")
print("=" * 60)

# 检查目录是否存在
for key in ['DB_DIR', 'UPLOAD_DIR']:
    path = app.config[key]
    exists = os.path.exists(path)
    print(f"{key:12} {'✅ 存在' if exists else '❌ 不存在'}: {path}")

    if not exists:
        os.makedirs(path, exist_ok=True)
        print(f"  → 已创建目录: {path}")

print("=" * 60)