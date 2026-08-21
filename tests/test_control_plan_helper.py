import unittest
from unittest.mock import patch

from app.control_plan_helper import (
    _align_ai_header, _extract_metadata, _find_header, _parse_aiag, _parse_process_record,
    assess_quality, extract_control_plan,
)


class ControlPlanParserTests(unittest.TestCase):
    def test_pdf_cover_metadata_stops_at_the_next_inline_label(self):
        text = (
            "零件号码：2D000936 零件名称：5寸TFT仪表 车型年度/车辆类型： Aprillia "
            "供应商名称/代码： 控制计划号码：A-CP-DIC104A-A1\n"
            "编制/日期：沈云开/ 2025.6.13 供应商批准/日期：沈云开/ 2025.6.13 "
            "修订日期：2026.6.12"
        )

        metadata = _extract_metadata([], text)

        self.assertEqual(metadata["part_number"], "2D000936")
        self.assertEqual(metadata["part_name"], "5寸TFT仪表")
        self.assertEqual(metadata["organization"], "")
        self.assertEqual(metadata["control_plan_number"], "A-CP-DIC104A-A1")
        self.assertEqual(metadata["compiled_date"], "沈云开/ 2025.6.13")

    def test_aiag_mapping_keeps_product_and_process_characteristics(self):
        matrix = [
            [
                "Part/Process Number", "Process name/operation description",
                "Production equipment", "Characteristic", "Characteristic",
                "Characteristic", "Classification of special characteristics",
                "Method", "Method", "Method", "Method", "Method",
                "Control Method", "Adverse reactions",
            ],
            [
                "", "", "", "Serial number", "Product item", "process", "",
                "Product/Process Specifications/Tolerances",
                "Evaluation/Measurement Technology", "sample", "sample",
                "sample", "", "",
            ],
            [
                "", "", "", "", "", "", "", "", "", "Capacity",
                "Frequency", "Inspectors", "", "",
            ],
            [
                "10", "Incoming inspection", "Caliper", "1", "Diameter", "",
                "CC", "10 +/- 0.1 mm", "Caliper", "3 pcs", "Each batch",
                "QC", "Inspection record", "Stop and segregate",
            ],
            [
                "10", "Incoming inspection", "Caliper", "1", "Diameter", "",
                "CC", "10 +/- 0.1 mm", "Caliper", "3 pcs", "Each batch",
                "QC", "Inspection record", "Stop and segregate",
            ],
            [
                "10", "Incoming inspection", "Caliper", "2", "", "Pressure",
                "", "0.5 MPa", "Pressure gauge", "1 pc", "Each shift",
                "Operator", "Process sheet", "Adjust and recheck",
            ],
        ]
        header = _find_header(matrix)
        self.assertEqual(header["kind"], "aiag")
        steps = _parse_aiag(matrix, header, "Control Plan")
        self.assertEqual(len(steps), 1)
        self.assertEqual(len(steps[0]["characteristics"]), 2)
        self.assertEqual(steps[0]["characteristics"][0]["char_type"], "product")
        self.assertEqual(steps[0]["characteristics"][1]["char_type"], "process")
        self.assertEqual(steps[0]["characteristics"][1]["char_name"], "Pressure")

    def test_process_record_template_splits_key_parameters(self):
        matrix = [
            ["No.", "Process Name", "Process Record", "Key Parameters"],
            ["1", "Flood Rinse", "Spray both sides", "Time: 3 min\nPressure: >=0.1 MPa"],
            ["2", "★ Phosphating", "Record tank chemistry", "Temperature: 35 C"],
        ]
        header = _find_header(matrix)
        self.assertEqual(header["kind"], "process_record")
        steps = _parse_process_record(matrix, header, "Process")
        self.assertEqual(len(steps), 2)
        self.assertEqual(len(steps[0]["characteristics"]), 2)
        self.assertTrue(steps[1]["is_key_process"])
        self.assertEqual(steps[0]["characteristics"][0]["char_name"], "Time")

    def test_aiag_parser_skips_document_metadata_and_keeps_continuation_rows(self):
        matrix = [
            ["生产阶段", "生产阶段", "样件", "", "主要联系人", "88511650"],
            ["控制计划编号", "控制计划编号", "", "", "", ""],
            ["零件/过程编号", "过程名称/操作描述", "机器、装置夹具、工装", "产品", "产品/过程标准/公差", "评价测量技术"],
            ["10", "来料检验", "卡尺", "直径", "10 +/- 0.1 mm", "卡尺"],
            ["", "", "", "外观", "无裂纹", "目测"],
        ]
        header = {
            "start": 2,
            "height": 1,
            "mapping": {
                "process_code": 0,
                "process_name": 1,
                "machine": 2,
                "product_char": 3,
                "specification": 4,
                "measurement_method": 5,
            },
        }
        steps = _parse_aiag(matrix, header, "Control Plan")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["process_name"], "来料检验")
        self.assertEqual(
            [item["char_name"] for item in steps[0]["characteristics"]],
            ["直径", "外观"],
        )

    def test_ai_header_uses_confident_rule_based_table_boundary(self):
        ai_header = {
            "kind": "aiag",
            "start": 0,
            "height": 1,
            "mapping": {"process_name": 1, "product_char": 3},
        }
        detected_header = {
            "kind": "aiag",
            "score": 12,
            "start": 9,
            "height": 3,
            "mapping": {},
        }
        aligned = _align_ai_header(ai_header, detected_header)
        self.assertEqual(aligned["start"], 9)
        self.assertEqual(aligned["height"], 3)
        self.assertEqual(aligned["mapping"], ai_header["mapping"])

    def test_quality_check_flags_incomplete_key_characteristic(self):
        data = {
            "steps": [{
                "process_name": "Machining",
                "characteristics": [{
                    "char_name": "Diameter",
                    "is_key_char": True,
                    "spec_value": "",
                    "measurement_method": "",
                    "sample_size": "1",
                    "frequency": "Each batch",
                    "control_method": "",
                    "reaction_plan": "",
                }],
            }]
        }
        score, issues = assess_quality(data)
        codes = {issue["code"] for issue in issues}
        self.assertLess(score, 100)
        self.assertIn("incomplete_key_characteristic", codes)
        self.assertIn("missing_spec", codes)

    def test_pdf_control_plan_uses_cross_page_table_matrix(self):
        matrix = [
            [
                "Part/Process Number", "Process name/operation description",
                "Production equipment", "Characteristic", "Characteristic",
                "Classification of special characteristics", "Method", "Method",
                "Method", "Control Method", "Adverse reactions",
            ],
            [
                "", "", "", "Product item", "Process", "",
                "Product/Process Specifications/Tolerances",
                "Evaluation/Measurement Technology", "Sample Frequency", "", "",
            ],
            [
                "10", "Incoming inspection", "Caliper", "Diameter", "", "CC",
                "10 +/- 0.1 mm", "Caliper", "Each batch", "Inspection record",
                "Stop and segregate",
            ],
            [
                "20", "Assembly", "Fixture", "", "Torque", "",
                "5 +/- 0.5 Nm", "Torque wrench", "Each shift", "Process sheet",
                "Adjust and recheck",
            ],
        ]
        pdf_sheet = [{
            "name": "PDF pages 1-2",
            "matrix": matrix,
            "metadata_text": "零件号码：2D000936\n控制计划号码：A-CP-001",
        }]

        with patch("app.control_plan_helper._read_pdf", return_value=pdf_sheet):
            data = extract_control_plan("supplier-control-plan.pdf", force_ai=True)

        self.assertEqual(data["source_template"], "pdf_aiag")
        self.assertEqual(data["ai_model"], None)
        self.assertEqual(len(data["steps"]), 2)
        self.assertEqual(data["metadata"]["part_number"], "2D000936")
        self.assertEqual(data["metadata"]["control_plan_number"], "A-CP-001")

    def test_adayo_bilingual_pdf_header_aliases_map_all_core_columns(self):
        matrix = [
            [
                "过程编号 Part/Process Number",
                "过程名称/操作描述 Process Name/Operation Description",
                "机器、设备、工装、夹具 Machine Device.Jig. Tool for Mfg",
                "编号 No.", "产品 Product", "过程 Process", "特殊特性分类",
                "产品/过程标准/公差 Product/Process Specification/Tolerance",
                "评估/测量方法 Evaluation Measurement Technique",
                "样本容量 samples QTY", "样本频率 sampling frequency",
                "负责人 Action Holder", "控制方法 Control Method",
                "操作规范/记录表单编号", "反应计划 Action plan",
            ],
            [
                "IQC01", "Incoming inspection", "Visual", "1", "Appearance", "",
                "", "No damage", "Visual", "100%", "Each batch", "Inspector",
                "Inspection record", "WI-001", "Stop and segregate",
            ],
        ]
        header = _find_header(matrix)
        self.assertEqual(header["mapping"]["machine"], 2)
        self.assertEqual(header["mapping"]["product_char"], 4)
        self.assertEqual(header["mapping"]["process_char"], 5)
        self.assertEqual(header["mapping"]["inspector"], 11)


if __name__ == "__main__":
    unittest.main()
