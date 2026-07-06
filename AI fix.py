# 保存为 test_8d.py，放在项目根目录跑
# python test_8d.py "你的8D文件完整路径"

import sys
from app.ai_helper import extract_text_from_file, extract_8d, is_ollama_available

file_path = sys.argv[1] if len(sys.argv) > 1 else input("8D file path: ").strip().strip('"')

print("=" * 50)
print(f"[1] File: {file_path}")

# Step 1: 文本提取
raw = extract_text_from_file(file_path)
print(f"[2] Text extracted: {len(raw)} chars")
if len(raw) < 50:
    print(f"    ❌ TOO SHORT! Content: {repr(raw[:200])}")
    sys.exit(1)
else:
    print(f"    ✅ First 300 chars:\n    {raw[:300]}")

# Step 2: Ollama 状态
print(f"\n[3] Ollama available: {is_ollama_available()}")
if not is_ollama_available():
    print("    ❌ Ollama not running! Start it first.")
    sys.exit(1)

# Step 3: AI 提取
print(f"\n[4] Calling AI extract_8d (may take 30-60s)...")
result = extract_8d(file_path)
print(f"\n[5] Result: {result}")

if result:
    print("\n" + "=" * 50)
    for k, v in result.items():
        status = "✅" if v else "⚠️ EMPTY"
        print(f"  {status} {k}: {v[:80] if v else ''}")
else:
    print("    ❌ extract_8d returned None")