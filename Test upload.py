"""
测试 TR 文档上传功能
运行方式: python test_upload.py
"""

from app import create_app, db
from app.models import TroubleReport, TRDocument
import os

app = create_app()

with app.app_context():
    print("=" * 60)
    print("🔍 测试 TR 文档上传功能")
    print("=" * 60)

    # 1. 检查配置
    upload_dir = app.config.get("UPLOAD_DIR")
    print(f"\n1️⃣ UPLOAD_DIR 配置: {upload_dir}")
    print(f"   目录是否存在: {os.path.exists(upload_dir) if upload_dir else 'N/A'}")

    # 2. 检查 TR 记录
    trs = TroubleReport.query.all()
    print(f"\n2️⃣ TR 记录数量: {len(trs)}")
    for tr in trs:
        print(f"   - TR#{tr.id}: {tr.tr_no} ({tr.supplier_name})")

    # 3. 检查文档记录
    docs = TRDocument.query.all()
    print(f"\n3️⃣ 文档记录数量: {len(docs)}")
    for doc in docs:
        print(f"   - 文档#{doc.id}: {doc.title} (TR#{doc.tr_id})")
        print(f"     类型: {doc.doc_type}, 大小: {doc.size} bytes")
        print(f"     路径: {doc.rel_path}")

        # 检查物理文件是否存在
        if upload_dir:
            full_path = os.path.join(upload_dir, doc.rel_path)
            exists = os.path.exists(full_path)
            print(f"     物理文件存在: {exists}")
            if exists:
                print(f"     实际大小: {os.path.getsize(full_path)} bytes")

    # 4. 检查 tr_docs 目录
    if upload_dir:
        tr_docs_dir = os.path.join(upload_dir, "tr_docs")
        print(f"\n4️⃣ tr_docs 目录: {tr_docs_dir}")
        print(f"   是否存在: {os.path.exists(tr_docs_dir)}")

        if os.path.exists(tr_docs_dir):
            subdirs = [d for d in os.listdir(tr_docs_dir) if os.path.isdir(os.path.join(tr_docs_dir, d))]
            print(f"   子目录数量: {len(subdirs)}")
            for subdir in subdirs:
                subdir_path = os.path.join(tr_docs_dir, subdir)
                files = [f for f in os.listdir(subdir_path) if os.path.isfile(os.path.join(subdir_path, f))]
                print(f"   - {subdir}: {len(files)} 个文件")

    # 5. 测试特定 TR 的文档
    if trs:
        test_tr = trs[0]
        doc_count = test_tr.documents.count()
        print(f"\n5️⃣ 测试 TR ({test_tr.tr_no}) 的文档:")
        print(f"   文档数量: {doc_count}")

        for doc in test_tr.documents:
            print(f"   - {doc.title}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)