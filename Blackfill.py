"""
backfill_lot.py — 回填已有 TR 的 lot 号
用法：在项目根目录跑 `python backfill_lot.py`

逻辑：
  - TR-EDC-xxx：从 OneDrive 找对应 PDF，提取 "Lot check.xxx"
  - 提取不到或 PDF 不存在：填 'N/A'
  - 非 EDC 的 TR（手动新建的）：填 'N/A'
  - 已有 lot_number 的不动
"""
import re
import sys
from pathlib import Path

try:
    from app import create_app
    from app.extensions import db
    from app.models import TroubleReport
except ImportError as e:
    print(f"❌ 请在项目根目录运行此脚本（和 flask run 同目录）\n{e}")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("❌ 请先安装：pip install pdfplumber")
    sys.exit(1)


def extract_lot(pdf_path):
    """从 PDF 文本中提取 Lot check 号"""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        m = re.search(r"Lot\s*check[.:]?\s*(\S+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None
    except Exception as e:
        print(f"    ! PDF 读取失败：{e}")
        return None


def main():
    app = create_app()
    with app.app_context():
        onedrive_str = app.config.get("EDC_ONEDRIVE_PATH", "")
        root = Path(onedrive_str) if onedrive_str else None
        if not root or not root.exists():
            print(f"⚠ OneDrive 路径不可用（{onedrive_str}），EDC TR 会全部标 N/A")
            root = None

        # 找需要回填的 TR
        targets = TroubleReport.query.filter(
            (TroubleReport.lot_number.is_(None)) | (TroubleReport.lot_number == "")
        ).all()
        print(f"找到 {len(targets)} 条需要回填的 TR\n")

        stats = {"found": 0, "edc_na": 0, "non_edc": 0}

        for tr in targets:
            m = re.match(r"TR-EDC-(\d+)", tr.tr_no)
            if not m:
                tr.lot_number = "N/A"
                stats["non_edc"] += 1
                continue

            edc_no = m.group(1)
            if not root:
                tr.lot_number = "N/A"
                stats["edc_na"] += 1
                continue

            # 找 PDF
            pdf_path = None
            for p in root.rglob(f"*{edc_no}*.pdf"):
                pdf_path = p
                break

            if not pdf_path:
                print(f"  [{tr.tr_no}] PDF 未找到 → N/A")
                tr.lot_number = "N/A"
                stats["edc_na"] += 1
                continue

            lot = extract_lot(pdf_path)
            if lot:
                tr.lot_number = lot
                stats["found"] += 1
                print(f"  [{tr.tr_no}] ✓ Lot {lot}")
            else:
                tr.lot_number = "N/A"
                stats["edc_na"] += 1
                print(f"  [{tr.tr_no}] PDF 内无 Lot → N/A")

        db.session.commit()
        print(f"\n✅ 完成")
        print(f"   成功提取：{stats['found']}")
        print(f"   EDC 但无 Lot：{stats['edc_na']}")
        print(f"   非 EDC（手动）：{stats['non_edc']}")


if __name__ == "__main__":
    main()