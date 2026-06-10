import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import bidflow


class BidflowTests(unittest.TestCase):
    def valid_source_readiness(self):
        return {
            "sources": [
                {
                    "source_id": "SRC-TENDER",
                    "file": "tender.pdf",
                    "source_type": "tender",
                    "source_role": "core",
                    "format": "pdf",
                    "exists": True,
                    "readability": "READABLE",
                    "text_extractable": True,
                    "table_extractable": True,
                    "structure_extractable": True,
                    "parse_confidence": "HIGH",
                    "contains_key_tables": True,
                    "manual_table_reviewed": False,
                    "requires_conversion": False,
                    "conversion_status": "NOT_REQUIRED",
                },
                {
                    "source_id": "SRC-SPEC",
                    "file": "technical-specification.pdf",
                    "source_type": "technical_specification",
                    "source_role": "core",
                    "format": "pdf",
                    "exists": True,
                    "readability": "READABLE",
                    "text_extractable": True,
                    "table_extractable": True,
                    "structure_extractable": True,
                    "parse_confidence": "HIGH",
                    "contains_key_tables": True,
                    "manual_table_reviewed": False,
                    "requires_conversion": False,
                    "conversion_status": "NOT_REQUIRED",
                },
            ]
        }

    def valid_scoring_applicability(self, package_name="package-1"):
        return {
            "scoring_groups": [
                {
                    "scoring_group_id": "SCG-001",
                    "source": {
                        "file": "tender.pdf",
                        "page": "40",
                        "original_scope_text": "This scoring group applies to the current package.",
                    },
                    "applies_to_packages": [package_name],
                    "excluded_packages": [],
                    "technical_weight": 60,
                    "business_weight": 10,
                    "price_weight": 30,
                    "selected_for_current_package": True,
                    "human_confirmed": True,
                }
            ]
        }

    def valid_requirements(self):
        return {
            "records": [
                {
                    "requirement_id": "REQ-0001",
                    "item_type": "technical_requirement",
                    "original_text": "投标人应提供实施方案。",
                    "atomic_requirement": "提供实施方案",
                    "source": {"file": "招标文件.pdf", "page": "12", "section_path": "第三章"},
                    "raw_markers": [],
                    "marker_flags": {"asterisk": False, "star": False, "rejection": False},
                    "response": {"required": True, "primary_chapter": "实施方案"},
                    "applicable_package": "标包A",
                    "score": {"score_item_id": "SCI-001"},
                }
            ]
        }

    def valid_chapter_plan(self):
        return {
            "sections": [
                {
                    "section_id": "SEC-001",
                    "level": 1,
                    "title": "实施方案",
                    "order": 1,
                    "source": {
                        "file": "招标文件.pdf",
                        "page": "20",
                        "section_path": "技术投标文件格式",
                        "original_text": "一、实施方案",
                    },
                    "locked_by_tender_format": True,
                    "mapped_scoring_item_ids": ["SCI-001"],
                    "mapped_requirement_ids": ["REQ-0001"],
                    "writing_task_ids": ["TASK-001"],
                }
            ],
            "scoring_item_mappings": [
                {
                    "scoring_item_id": "SCI-001",
                    "score_value": 10,
                    "primary_section_id": "SEC-001",
                    "supporting_section_ids": [],
                    "split_into_tasks": ["TASK-001"],
                    "mapping_rationale": "按格式章节响应实施方案评分项",
                    "coverage_risk": "LOW",
                }
            ],
            "technical_requirement_mappings": [
                {
                    "requirement_id": "REQ-0001",
                    "primary_section_id": "SEC-001",
                    "supporting_section_ids": [],
                    "mapping_rationale": "实施方案章节直接响应",
                }
            ],
            "writing_tasks": [
                {
                    "task_id": "TASK-001",
                    "target_section_ids": ["SEC-001"],
                    "task_title": "实施方案",
                    "reason_for_split": "单章独立写作",
                    "scoring_item_ids": ["SCI-001"],
                    "requirement_ids": ["REQ-0001"],
                    "output_file": "chapters/implementation.md",
                }
            ],
            "manual_confirmations": [],
        }

    def test_slugify_removes_windows_invalid_characters(self):
        self.assertEqual(bidflow.slugify('A/B:C*D?'), "A-B-C-D-")

    def test_load_json_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bom.json"
            path.write_text('\ufeff{"records": []}', encoding="utf-8")

            data = bidflow.load_json(path)

            self.assertEqual(data["records"], [])

    def test_validate_blocks_unconfirmed_project(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            project = bidflow.load_json(bidflow.PROJECT_TEMPLATE)
            project["project_name"] = "测试项目"
            project["package_name"] = "标包1"
            bidflow.write_json(project_dir / "project.json", project)

            errors = bidflow.validate_project(project_dir)

            self.assertTrue(any("当前标包尚未人工确认" in item for item in errors))
            self.assertTrue(any("缺少 requirements/atomic-requirements.json" in item for item in errors))
            self.assertTrue(any("缺少 requirements/marker-register.json" in item for item in errors))
            self.assertTrue(any("缺少 requirements/scoring-map.json" in item for item in errors))
            self.assertTrue(any("缺少 inventory/source-readiness.json" in item for item in errors))
            self.assertTrue(any("缺少 requirements/scoring-applicability.json" in item for item in errors))

    def test_init_and_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(bidflow, "ROOT", root):
                with patch.object(bidflow, "PROJECT_TEMPLATE", Path(__file__).parents[1] / "templates" / "project.json"):
                    with patch.object(bidflow, "WORKFLOW", Path(__file__).parents[1] / "config" / "workflow.json"):
                        with patch.object(
                            bidflow,
                            "AGENT_CONTRACTS",
                            Path(__file__).parents[1] / "config" / "agent-contracts.json",
                        ):
                            with patch.object(
                                bidflow,
                                "MINIMALISM_ROUTER",
                                Path(__file__).parents[1] / "config" / "minimalism-router.json",
                            ):
                                project_dir = bidflow.init_project("示例项目", "标包A")
                                plan_path = bidflow.build_plan(project_dir)
                                state_exists = (project_dir / "state" / "workflow-state.json").exists()

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["mode"], "subagent")
        self.assertEqual(plan["package_name"], "标包A")
        self.assertIn("minimalism_router", plan)
        self.assertIn("state_handoff", plan)
        self.assertTrue(state_exists)

    def test_validate_expansion_accepts_matching_threefold_structure(self):
        source = "# 标题\n\n我司依据既定要求开展检查，逐项记录发现事项。"
        expanded = (
            "# 标题\n\n"
            "我司依据既定要求组织开展检查工作，结合原有检查范围逐项核验执行情况，"
            "同步记录检查过程、检查依据和发现事项，并按照既有处理要求推进问题核对、"
            "过程留痕和后续衔接工作。"
        )

        report = bidflow.validate_expansion(source, expanded)

        self.assertTrue(report["structure_matches"])
        self.assertEqual(report["status"], "PASS")

    def test_execution_plan_contains_expansion_stage_and_contract(self):
        workflow = bidflow.load_json(bidflow.WORKFLOW)
        contracts = bidflow.load_json(bidflow.AGENT_CONTRACTS)

        stage_ids = [stage["id"] for stage in workflow["stages"]]
        self.assertIn("expansion", stage_ids)
        self.assertIn("chapter-expander-*", contracts["agents"])

    def test_planning_stage_requires_chapter_plan_before_tasks(self):
        workflow = bidflow.load_json(bidflow.WORKFLOW)
        contracts = bidflow.load_json(bidflow.AGENT_CONTRACTS)
        planning_stage = next(stage for stage in workflow["stages"] if stage["id"] == "planning")
        chapter_planner = contracts["agents"]["chapter-planner"]

        self.assertIn("planning/chapter-plan.json", planning_stage["outputs"])
        self.assertIn("planning/chapter-plan.json", chapter_planner["writes"])
        self.assertTrue(any("技术投标文件格式" in item for item in chapter_planner["must_do"]))
        self.assertTrue(any("直接生成正文" in item for item in chapter_planner["must_not"]))

    def test_validate_project_requires_chapter_plan_for_planning_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            (project_dir / "tasks").mkdir(parents=True, exist_ok=True)

            errors = bidflow.collect_stage_errors(project_dir, "planning")

            self.assertTrue(any("planning/chapter-plan.json" in item for item in errors))

    def test_intake_and_writer_contracts_include_lightweight_rag_gate(self):
        workflow = bidflow.load_json(bidflow.WORKFLOW)
        contracts = bidflow.load_json(bidflow.AGENT_CONTRACTS)
        intake_stage = next(stage for stage in workflow["stages"] if stage["id"] == "intake")
        writer = contracts["agents"]["chapter-writer-*"]

        self.assertIn("inventory/rag-fragments.json", intake_stage["outputs"])
        self.assertTrue(any("DISABLED" in item for item in writer["must_not"]))
        self.assertTrue(any("original_content" in item for item in writer["must_not"]))

    def test_minimalism_review_passes_current_workflow(self):
        report = bidflow.review_minimalism(
            bidflow.load_json(bidflow.WORKFLOW),
            bidflow.load_json(bidflow.MINIMALISM_ROUTER),
        )

        self.assertEqual(report["status"], "PASS")
        self.assertTrue(any(stage["id"] == "review" and stage["default_execution_level"] == "L0" for stage in report["stages"]))
        self.assertTrue(
            all(
                stage["context_policy"]
                for stage in report["stages"]
                if stage["default_execution_level"] in {"L2", "L3", "L4"}
            )
        )

    def test_source_readiness_blocks_untrusted_core_doc(self):
        data = self.valid_source_readiness()
        data["sources"][1].update(
            {
                "file": "technical-specification.doc",
                "format": "doc",
                "readability": "UNREADABLE",
                "text_extractable": False,
                "table_extractable": False,
                "requires_conversion": True,
                "conversion_target": "pdf",
                "conversion_status": "PENDING",
            }
        )

        report = bidflow.validate_source_readiness(data)

        self.assertEqual(report["status"], "REJECT")
        self.assertGreaterEqual(report["blocking_source_count"], 1)

    def test_source_readiness_allows_readable_core_doc(self):
        data = self.valid_source_readiness()
        data["sources"][1].update(
            {
                "file": "technical-specification.doc",
                "format": "doc",
                "readability": "READABLE",
                "text_extractable": True,
                "table_extractable": True,
                "structure_extractable": True,
                "parse_confidence": "HIGH",
                "requires_conversion": True,
                "conversion_target": "docx",
                "conversion_status": "DONE",
            }
        )

        report = bidflow.validate_source_readiness(data)

        self.assertEqual(report["status"], "PASS")

    def test_source_readiness_degrades_unreadable_reference_material(self):
        data = self.valid_source_readiness()
        data["sources"].append(
            {
                "source_id": "SRC-HIS",
                "file": "historical-bid.doc",
                "source_type": "historical_bid",
                "source_role": "reference",
                "format": "doc",
                "exists": True,
                "readability": "UNREADABLE",
                "text_extractable": False,
                "table_extractable": False,
                "structure_extractable": False,
                "parse_confidence": "LOW",
                "contains_key_tables": False,
                "manual_table_reviewed": False,
                "requires_conversion": True,
                "conversion_target": "docx",
                "conversion_status": "PENDING",
            }
        )

        report = bidflow.validate_source_readiness(data)

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["blocking_source_count"], 0)
        self.assertTrue(any(item.get("action") == "降低引用优先级或排除出 RAG 检索范围" for item in report["findings"]))

    def test_source_readiness_blocks_unreviewed_key_tables(self):
        data = self.valid_source_readiness()
        data["sources"][0].update({"table_extractable": False, "contains_key_tables": True, "manual_table_reviewed": False})

        report = bidflow.validate_source_readiness(data)

        self.assertEqual(report["status"], "REJECT")

    def test_ingest_sources_writes_index_and_readiness_for_text_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            (project_dir / "sources" / "tender").mkdir(parents=True)
            (project_dir / "sources" / "technical-specification").mkdir(parents=True)
            (project_dir / "sources" / "tender" / "tender.txt").write_text("第一章 招标要求\n\n投标人应提供方案。", encoding="utf-8")
            (project_dir / "sources" / "technical-specification" / "spec.txt").write_text("一、技术规范\n\n满足系统建设要求。", encoding="utf-8")
            project = bidflow.load_json(bidflow.PROJECT_TEMPLATE)
            project.update({"project_name": "测试项目", "package_name": "标包A", "package_confirmed": True})
            bidflow.write_json(project_dir / "project.json", project)

            report = bidflow.ingest_sources(project_dir)

            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["source_count"], 2)
            self.assertGreaterEqual(report["fragment_count"], 2)
            readiness = bidflow.load_json(project_dir / "inventory" / "source-readiness.json")
            source_index = bidflow.load_json(project_dir / "inventory" / "source-index.json")
            self.assertEqual(len(readiness["sources"]), 2)
            self.assertTrue(any(item["source_type"] == "tender" for item in readiness["sources"]))
            self.assertTrue(any(fragment["location"].get("section_path") for fragment in source_index["fragments"]))

    def test_ingest_sources_records_xlsx_table_location(self):
        openpyxl = bidflow.try_import("openpyxl")
        if openpyxl is None:
            self.skipTest("openpyxl not installed")
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            (project_dir / "sources" / "technical-specification").mkdir(parents=True)
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = "评分表"
            sheet.append(["评分项", "分值"])
            sheet.append(["实施方案", 10])
            workbook.save(project_dir / "sources" / "technical-specification" / "score.xlsx")
            project = bidflow.load_json(bidflow.PROJECT_TEMPLATE)
            project.update({"project_name": "测试项目", "package_name": "标包A", "package_confirmed": True})
            project["sources"]["tender"] = ["sources/technical-specification/score.xlsx"]
            project["sources"]["technical_specification"] = ["sources/technical-specification/score.xlsx"]
            bidflow.write_json(project_dir / "project.json", project)

            report = bidflow.ingest_sources(project_dir)

            self.assertEqual(report["status"], "PASS")
            source_index = bidflow.load_json(project_dir / "inventory" / "source-index.json")
            table_fragments = [fragment for fragment in source_index["fragments"] if fragment["kind"] == "table"]
            self.assertTrue(table_fragments)
            self.assertEqual(table_fragments[0]["location"]["table"]["sheet"], "评分表")

    def test_scoring_applicability_requires_one_confirmed_matching_group(self):
        report = bidflow.validate_scoring_applicability(
            self.valid_scoring_applicability("package-1"),
            "package-1",
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["selected_group_count"], 1)

    def test_scoring_applicability_allows_package_alias(self):
        report = bidflow.validate_scoring_applicability(
            self.valid_scoring_applicability("标包6-1：2026-2027年信息化项目文件评审和估算评审框架采购"),
            "6-1",
        )

        self.assertEqual(report["status"], "PASS")

    def test_scoring_applicability_does_not_confuse_similar_package_codes(self):
        report = bidflow.validate_scoring_applicability(
            self.valid_scoring_applicability("标包6-10：其他框架采购"),
            "6-1",
        )

        self.assertEqual(report["status"], "REJECT")

    def test_scoring_applicability_blocks_wrong_or_duplicate_group(self):
        wrong_package = self.valid_scoring_applicability("other-package")
        wrong_report = bidflow.validate_scoring_applicability(wrong_package, "package-1")

        duplicate = self.valid_scoring_applicability("package-1")
        duplicate["scoring_groups"].append(
            {
                "scoring_group_id": "SCG-002",
                "source": {
                    "file": "tender.pdf",
                    "page": "50",
                    "original_scope_text": "This scoring group also applies to package-1.",
                },
                "applies_to_packages": ["package-1"],
                "selected_for_current_package": True,
                "human_confirmed": True,
            }
        )
        duplicate_report = bidflow.validate_scoring_applicability(duplicate, "package-1")

        self.assertEqual(wrong_report["status"], "REJECT")
        self.assertEqual(duplicate_report["status"], "REJECT")

    def test_validate_chapter_plan_accepts_covered_requirements_and_scoring(self):
        report = bidflow.validate_chapter_plan(
            self.valid_chapter_plan(),
            self.valid_requirements(),
            {"items": [{"scoring_item_id": "SCI-001"}]},
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["mapped_requirement_count"], 1)
        self.assertEqual(report["mapped_scoring_item_count"], 1)

    def test_validate_chapter_plan_blocks_missing_mandatory_mapping(self):
        plan = self.valid_chapter_plan()
        plan["sections"][0]["mapped_requirement_ids"] = []
        plan["technical_requirement_mappings"] = []
        plan["writing_tasks"][0]["requirement_ids"] = []

        report = bidflow.validate_chapter_plan(plan, self.valid_requirements(), {})

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("强制/必答原子要点未映射" in item["message"] for item in report["findings"]))

    def test_shred_rfp_writes_outputs_and_reuses_requirement_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            shred_file = project_dir / "shred.json"
            marker_register = {
                "markers": [
                    {
                        "marker_id": "MARK-001",
                        "raw_marker": "*",
                        "meaning": "重要条款",
                        "meaning_source": {"file": "招标文件.pdf", "original_text": "* 表示重要条款"},
                        "confirmed": True,
                    }
                ]
            }
            rejection_clauses = {"clauses": []}
            bidflow.write_json(
                shred_file,
                {
                    "outputs": {
                        "atomic_requirements": self.valid_requirements(),
                        "marker_register": marker_register,
                        "rejection_clauses": rejection_clauses,
                        "scoring_map": {"items": [{"scoring_item_id": "SCI-001"}]},
                        "exclusion_list": {"items": []},
                    }
                },
            )

            report = bidflow.shred_rfp(project_dir, shred_file)

            self.assertEqual(report["status"], "PASS")
            self.assertTrue((project_dir / "requirements" / "atomic-requirements.json").exists())
            self.assertTrue((project_dir / "requirements" / "scoring-map.json").exists())

    def test_validate_expansion_accepts_utf8_bom_before_heading(self):
        source = "\ufeff# 标题\n\n我司依据既定要求开展检查，逐项记录发现事项。"
        expanded = (
            "\ufeff# 标题\n\n"
            "我司依据既定要求组织开展检查工作，结合原有检查范围逐项核验执行情况，"
            "同步记录检查过程、检查依据和发现事项，并按照既有处理要求推进问题核对、"
            "过程留痕和后续衔接工作。"
        )

        report = bidflow.validate_expansion(source, expanded)

        self.assertEqual(report["status"], "PASS")

    def test_validate_expansion_rejects_summary_boundaries_and_structure_change(self):
        source = "# 标题\n\n我司开展检查。"
        expanded = "# 标题\n\n综上所述，我司开展检查并形成记录。\n\n由此可见。"

        report = bidflow.validate_expansion(source, expanded)

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("分段数量不一致" in item for item in report["findings"]))
        self.assertTrue(any("总结式段首" in item for item in report["findings"]))

    def test_validate_requirement_register_accepts_confirmed_atomic_items(self):
        data = {
            "records": [
                {
                    "requirement_id": "REQ-0001",
                    "item_type": "technical_requirement",
                    "original_text": "* 投标人应提供实施方案。",
                    "atomic_requirement": "提供实施方案",
                    "source": {"file": "招标文件.pdf", "page": "12", "section_path": "第三章"},
                    "raw_markers": ["*"],
                    "marker_flags": {"asterisk": True, "star": False, "rejection": False},
                    "marker_meaning_confirmed": True,
                    "response": {"primary_chapter": "实施方案"},
                    "applicable_package": "标包A",
                }
            ]
        }

        report = bidflow.validate_requirement_register(data)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["marked_item_count"], 1)

    def test_validate_requirement_register_blocks_unconfirmed_rejection_clause(self):
        data = {
            "records": [
                {
                    "requirement_id": "REQ-0002",
                    "item_type": "rejection_clause",
                    "original_text": "未提供技术方案的，作废标处理。",
                    "atomic_requirement": "必须提供技术方案",
                    "source": {"file": "招标文件.pdf", "section_path": "废标条款"},
                    "raw_markers": ["废标"],
                    "marker_flags": {"asterisk": False, "star": False, "rejection": True},
                    "marker_meaning_confirmed": True,
                    "rejection_consequence": {
                        "trigger_condition": "未提供技术方案",
                        "consequence_text": "作废标处理",
                        "human_confirmed": False,
                    },
                    "response": {"primary_chapter": "实施方案"},
                    "applicable_package": "标包A",
                }
            ]
        }

        report = bidflow.validate_requirement_register(data)

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("尚未人工确认" in item["message"] for item in report["findings"]))

    def test_marker_register_rejects_empty_markers(self):
        report = bidflow.validate_marker_register({"markers": []})

        self.assertEqual(report["status"], "REJECT")

    def test_rejection_cross_refs_block_missing_atomic_requirement(self):
        report = bidflow.validate_requirement_cross_refs(
            {"records": []},
            {"markers": []},
            {"clauses": [{"requirement_id": "REQ-MISSING"}]},
        )

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("不存在于原子要点台账" in item["message"] for item in report["findings"]))

    def test_validate_project_export_requires_downstream_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            for directory in ("inventory", "requirements", "tasks", "chapters", "expanded", "evidence", "merged", "reviews"):
                (project_dir / directory).mkdir(parents=True, exist_ok=True)
            project = bidflow.load_json(bidflow.PROJECT_TEMPLATE)
            project.update(
                {
                    "project_name": "测试项目",
                    "package_name": "标包1",
                    "package_confirmed": True,
                    "document_format_confirmed": True,
                    "sources": {
                        "tender": ["招标文件.pdf"],
                        "technical_specification": ["技术规范书.pdf"],
                        "historical_reference": [],
                        "supporting_material": [],
                    },
                }
            )
            bidflow.write_json(project_dir / "project.json", project)
            bidflow.write_json(project_dir / "inventory" / "source-readiness.json", self.valid_source_readiness())
            bidflow.write_json(
                project_dir / "requirements" / "atomic-requirements.json",
                {
                    "records": [
                        {
                            "requirement_id": "REQ-0001",
                            "item_type": "technical_requirement",
                            "original_text": "投标人应提供方案。",
                            "atomic_requirement": "提供方案",
                            "source": {"file": "招标文件.pdf", "page": "1"},
                            "raw_markers": [],
                            "marker_flags": {},
                            "response": {"primary_chapter": "方案"},
                            "applicable_package": "标包1",
                        }
                    ]
                },
            )
            bidflow.write_json(
                project_dir / "requirements" / "marker-register.json",
                {
                    "markers": [
                        {
                            "marker_id": "MARK-001",
                            "raw_marker": "*",
                            "meaning": "重要条款",
                            "meaning_source": {
                                "file": "招标文件.pdf",
                                "original_text": "* 表示重要条款",
                            },
                            "confirmed": True,
                        }
                    ]
                },
            )
            bidflow.write_json(project_dir / "requirements" / "rejection-clauses.json", {"clauses": []})
            bidflow.write_json(project_dir / "requirements" / "scoring-map.json", {})
            bidflow.write_json(
                project_dir / "requirements" / "scoring-applicability.json",
                self.valid_scoring_applicability("标包1"),
            )
            bidflow.write_json(project_dir / "requirements" / "exclusion-list.json", {})

            requirement_errors = bidflow.validate_project(project_dir, stage="requirements")
            export_errors = bidflow.validate_project(project_dir, stage="export")

            self.assertFalse(any("merged/technical-bid-draft.md" in item for item in requirement_errors))
            self.assertTrue(any("merged/technical-bid-draft.md" in item for item in export_errors))


if __name__ == "__main__":
    unittest.main()
