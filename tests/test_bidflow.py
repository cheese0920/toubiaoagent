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

    def valid_scoring_map(self):
        return {
            "items": [
                {
                    "scoring_item_id": "SCI-001",
                    "detailed_review_element": "服务方案结构",
                    "score_value": 10,
                    "source": {
                        "file": "招标文件.pdf",
                        "page": "20",
                        "section_path": "技术评审",
                        "original_text": "结合项目实际，服务方案结构清晰、内容完整。",
                    },
                    "evaluation_method": {"original_text": "横向比较各投标人方案", "not_a_heading": True},
                    "highest_score_band": {
                        "score_range": "8-10",
                        "original_text": "结合项目实际，服务方案结构清晰、内容完整。",
                    },
                    "global_constraints": [
                        {
                            "constraint_id": "SGC-001-01",
                            "order": 1,
                            "original_phrase": "结合项目实际",
                            "constraint_type": "project_specificity",
                            "apply_to_all_atoms": True,
                        }
                    ],
                    "score_atoms": [
                        {
                            "score_atom_id": "SCA-001-01",
                            "order": 1,
                            "original_phrase": "服务方案结构清晰、内容完整",
                            "response_object": "服务内容完整性",
                            "atom_type": "content_object",
                            "heading_required": True,
                            "quality_criteria": ["结构清晰"],
                            "evidence_requirements": [],
                        }
                    ],
                }
            ]
        }

    def valid_scoring_applicability_v2(self):
        return {
            "version": 2,
            "current_package": {
                "package_id": "PKG-6-1",
                "canonical_name": "标包6-1 信息化项目评审",
                "aliases": ["6-1"],
                "human_confirmed": True,
            },
            "source_documents": [
                {"source_id": "SRC-TENDER", "file": "招标文件.pdf", "version": "2026-06-01"}
            ],
            "selected_scoring_group_ids": ["SCG-GLOBAL", "SCG-6-1"],
            "excluded_scoring_group_ids": ["SCG-OTHER"],
            "composition_mode": "UNION_WITH_OVERRIDE",
            "scoring_groups": [
                {
                    "scoring_group_id": "SCG-GLOBAL",
                    "group_type": "GLOBAL_COMMON",
                    "source_segments": [
                        {
                            "segment_id": "SEG-GLOBAL",
                            "source_id": "SRC-TENDER",
                            "location_type": "DOCX_SECTION",
                            "start_locator": {"section_path": "通用评审要求"},
                            "end_locator": {},
                            "original_scope_text": "本部分适用于全部标包。",
                        }
                    ],
                    "applicability_rules": [
                        {
                            "rule_id": "APR-GLOBAL",
                            "target_type": "PROJECT",
                            "package_ids": [],
                            "package_names": [],
                            "original_text": "本部分适用于全部标包。",
                        }
                    ],
                    "selection_status": "SELECTED",
                    "selected_for_current_package": True,
                    "human_confirmed": True,
                },
                {
                    "scoring_group_id": "SCG-6-1",
                    "group_type": "PACKAGE_SPECIFIC",
                    "source_segments": [
                        {
                            "segment_id": "SEG-6-1",
                            "source_id": "SRC-TENDER",
                            "location_type": "PDF_RANGE",
                            "start_locator": {"page": "40", "anchor_text": "标包6-1"},
                            "end_locator": {"page": "43", "anchor_text": "评分合计"},
                            "original_scope_text": "以下评分标准适用于标包6-1。",
                        }
                    ],
                    "applicability_rules": [
                        {
                            "rule_id": "APR-6-1",
                            "target_type": "PACKAGE",
                            "package_ids": ["PKG-6-1"],
                            "package_names": ["标包6-1 信息化项目评审"],
                            "original_text": "以下评分标准适用于标包6-1。",
                        }
                    ],
                    "selection_status": "SELECTED",
                    "selected_for_current_package": True,
                    "human_confirmed": True,
                },
                {
                    "scoring_group_id": "SCG-OTHER",
                    "group_type": "PACKAGE_SPECIFIC",
                    "source_segments": [
                        {
                            "segment_id": "SEG-OTHER",
                            "source_id": "SRC-TENDER",
                            "location_type": "XLSX_RANGE",
                            "start_locator": {"sheet": "评分表", "cell": "A50"},
                            "end_locator": {"sheet": "评分表", "cell": "H60"},
                            "original_scope_text": "本表适用于其他标包。",
                        }
                    ],
                    "applicability_rules": [
                        {
                            "rule_id": "APR-OTHER",
                            "target_type": "PACKAGE",
                            "package_ids": ["PKG-OTHER"],
                            "package_names": ["其他标包"],
                            "original_text": "本表适用于其他标包。",
                        }
                    ],
                    "selection_status": "EXCLUDED",
                    "selected_for_current_package": False,
                    "human_confirmed": True,
                },
            ],
            "unresolved_conflicts": [],
        }

    def valid_response_register(self):
        return {
            "version": 1,
            "project_name": "信息化项目文件评审",
            "package_id": "PKG-6-1",
            "package_name": "标包6-1",
            "records": [
                {
                    "response_item_id": "RSP-0001",
                    "requirement_id": "REQ-0001",
                    "record_type": "SUPPLIER_OBLIGATION",
                    "source_requirement": {
                        "original_text": "集中评审阶段不少于1人现场联络。",
                        "source_actor": "SUPPLIER",
                        "action": "安排",
                        "object": "现场联络人员",
                        "trigger_condition": "集中评审阶段",
                        "scope": "集中评审现场联络",
                        "parameters": [{"name": "人数", "operator": ">=", "value": "1", "unit": "人"}],
                    },
                    "response_mode": "DIRECT_COMMITMENT",
                    "canonical_response": "我司将在集中评审阶段安排不少于1人负责现场联络。",
                    "fixed_elements": ["集中评审阶段", "不少于1人", "现场联络"],
                    "allowed_expansion": ["联络事项登记", "会议通知传递", "问题反馈跟踪"],
                    "forbidden_changes": ["全周期驻场"],
                    "source_refs": [{"source_id": "SRC-SPEC", "page": "12"}],
                    "status": "CONFIRMED",
                    "human_confirmed": True,
                    "required_in_document": True,
                }
            ],
            "conflicts": [],
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
                },
                {
                    "section_id": "SEC-001-01",
                    "level": 2,
                    "title": "服务方案结构",
                    "order": 2,
                    "source": {},
                    "locked_by_tender_format": False,
                    "parent_section_id": "SEC-001",
                    "hierarchy_role": "scoring_element",
                    "derived_from": "detailed_review_element",
                    "scoring_derivation": {
                        "scoring_item_id": "SCI-001",
                        "detailed_review_element": "服务方案结构",
                        "score_description_excerpt": "服务方案结构清晰、内容完整",
                        "decomposition_keywords": ["结构清晰", "内容完整"],
                        "mapped_in_score_order": True,
                    },
                    "mapped_scoring_item_ids": ["SCI-001"],
                    "mapped_requirement_ids": ["REQ-0001"],
                    "writing_task_ids": ["TASK-001"],
                },
                {
                    "section_id": "SEC-001-01-01",
                    "level": 3,
                    "title": "服务内容完整性",
                    "order": 3,
                    "source": {},
                    "locked_by_tender_format": False,
                    "parent_section_id": "SEC-001-01",
                    "hierarchy_role": "scoring_description_breakdown",
                    "derived_from": "score_description",
                    "scoring_derivation": {
                        "scoring_item_id": "SCI-001",
                        "detailed_review_element": "服务方案结构",
                        "score_description_excerpt": "服务方案结构清晰、内容完整",
                        "highest_score_band_text": "结合项目实际，服务方案结构清晰、内容完整。",
                        "score_atom_ids": ["SCA-001-01"],
                        "response_object": "服务内容完整性",
                        "decomposition_keywords": ["内容完整"],
                        "quality_criteria": ["结构清晰"],
                        "global_constraint_ids": ["SGC-001-01"],
                        "mapping_role": "primary",
                        "mapped_in_score_order": True,
                    },
                    "mapped_scoring_item_ids": ["SCI-001"],
                    "mapped_requirement_ids": ["REQ-0001"],
                    "writing_task_ids": ["TASK-001"],
                }
            ],
            "scoring_item_mappings": [
                {
                    "scoring_item_id": "SCI-001",
                    "score_value": 10,
                    "detailed_review_element": "服务方案结构",
                    "score_description_excerpt": "服务方案结构清晰、内容完整",
                    "highest_score_band_text": "结合项目实际，服务方案结构清晰、内容完整。",
                    "decomposed_subpoints": ["结构清晰", "内容完整"],
                    "global_constraints": [
                        {
                            "constraint_id": "SGC-001-01",
                            "original_phrase": "结合项目实际",
                        }
                    ],
                    "writing_quality_criteria": ["结构清晰"],
                    "primary_section_id": "SEC-001",
                    "supporting_section_ids": [],
                    "score_atom_mappings": [
                        {
                            "score_atom_id": "SCA-001-01",
                            "order": 1,
                            "original_phrase": "服务方案结构清晰、内容完整",
                            "response_object": "服务内容完整性",
                            "primary_section_id": "SEC-001-01-01",
                            "supporting_section_ids": [],
                            "response_strategy": "single_primary_only",
                            "quality_criteria": ["结构清晰"],
                            "global_constraint_ids": ["SGC-001-01"],
                        }
                    ],
                    "mapped_section_hierarchy": [
                        {
                            "section_id": "SEC-001-01",
                            "level": 2,
                            "mapping_role": "detailed_review_element",
                        },
                        {
                            "section_id": "SEC-001-01-01",
                            "level": 3,
                            "mapping_role": "score_description_breakdown",
                        },
                    ],
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

    def valid_chapter_task(self):
        return {
            "task_id": "TASK-001",
            "title": "实施方案",
            "owner_agent": "chapter-realizer-*",
            "grounding_pack_file": "grounding/implementation.json",
            "paragraph_plan_file": "paragraph-plans/implementation.json",
            "planned_outline": [
                {
                    "section_id": "SEC-001",
                    "level": 1,
                    "title": "实施方案",
                    "scoring_item_ids": ["SCI-001"],
                    "requirement_ids": ["REQ-0001"],
                },
                {
                    "section_id": "SEC-001-01",
                    "level": 2,
                    "title": "服务方案结构",
                    "scoring_item_ids": ["SCI-001"],
                    "requirement_ids": ["REQ-0001"],
                },
            ],
            "scoring_items": [{"scoring_item_id": "SCI-001"}],
            "atomic_requirement_ids": ["REQ-0001"],
            "rejection_clause_ids": ["REJ-001"],
        }

    def valid_grounding_pack(self):
        return {
            "task_id": "TASK-001",
            "target_section_ids": ["SEC-001"],
            "planned_outline_refs": [{"section_id": "SEC-001", "level": 1, "title": "实施方案"}],
            "scoring_refs": [{"scoring_item_id": "SCI-001", "highest_score_band_text": "结合项目实际，服务方案结构清晰、内容完整。"}],
            "score_atom_refs": [{"score_atom_id": "SCA-001-01", "response_object": "服务内容完整性", "primary_section_id": "SEC-001"}],
            "technical_requirement_refs": [{"requirement_id": "REQ-0001", "original_text": "投标人应提供实施方案。", "source_ref": "SRC-TENDER"}],
            "project_facts": [{"fact_id": "FACT-001", "fact": "本项目需要形成实施方案。", "source_ref": "SRC-SPEC"}],
            "project_keywords": ["实施方案", "资料核查", "问题清单"],
            "required_actions": ["核查", "记录", "反馈"],
            "deliverables": ["问题清单", "实施记录"],
            "knowledge_cards": [{"path": "references/implementation/knowledge-card.md", "usage": "structure_and_expression_reference_only"}],
            "source_refs": [
                {"source_id": "SRC-TENDER", "file": "招标文件.pdf"},
                {"source_id": "SRC-SPEC", "file": "技术规范书.pdf"},
            ],
            "forbidden_claims": ["不得承诺未经确认的响应时限"],
            "rejection_clause_ids": ["REJ-001"],
        }

    def valid_paragraph_plan(self):
        return {
            "task_id": "TASK-001",
            "grounding_pack_file": "grounding/implementation.json",
            "paragraphs": [
                {
                    "paragraph_plan_id": "PP-001",
                    "section_id": "SEC-001",
                    "section_title": "实施方案",
                    "response_object": "服务内容完整性",
                    "scoring_item_ids": ["SCI-001"],
                    "score_atom_ids": ["SCA-001-01"],
                    "requirement_ids": ["REQ-0001"],
                    "project_actual": "本项目需要形成实施方案并覆盖资料核查和问题反馈。",
                    "required_actions": ["核查", "记录", "反馈"],
                    "control_points": ["资料完整性", "问题闭环"],
                    "deliverables": ["问题清单", "实施记录"],
                    "source_refs": [{"source_id": "SRC-TENDER", "file": "招标文件.pdf"}],
                    "rejection_clause_ids": ["REJ-001"],
                    "forbidden_claims": ["不得承诺未经确认的响应时限"],
                }
            ],
        }

    def valid_rejection_clauses(self):
        return {
            "clauses": [
                {
                    "clause_id": "REJ-001",
                    "clause_type": "rejection",
                    "original_text": "投标文件不得存在实质性不响应。",
                    "applicable": True,
                    "confirmed": True,
                    "source": {"file": "招标文件.pdf"},
                }
            ]
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
                                grounding_exists = (project_dir / "grounding").is_dir()
                                paragraph_plans_exists = (project_dir / "paragraph-plans").is_dir()

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["mode"], "subagent")
        self.assertEqual(plan["package_name"], "标包A")
        self.assertIn("minimalism_router", plan)
        self.assertIn("state_handoff", plan)
        self.assertTrue(state_exists)
        self.assertTrue(grounding_exists)
        self.assertTrue(paragraph_plans_exists)

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
        realizer = contracts["agents"]["chapter-realizer-*"]

        self.assertIn("inventory/rag-fragments.json", intake_stage["outputs"])
        self.assertTrue(any("DISABLED" in item for item in writer["must_not"]))
        self.assertTrue(any("original_content" in item for item in realizer["must_not"]))

    def test_drafting_stage_uses_realizer_before_expander(self):
        workflow = bidflow.load_json(bidflow.WORKFLOW)
        contracts = bidflow.load_json(bidflow.AGENT_CONTRACTS)
        stage_ids = [stage["id"] for stage in workflow["stages"]]
        grounding_stage = next(stage for stage in workflow["stages"] if stage["id"] == "grounding")
        drafting_stage = next(stage for stage in workflow["stages"] if stage["id"] == "drafting")

        self.assertLess(stage_ids.index("grounding"), stage_ids.index("drafting"))
        self.assertEqual(drafting_stage["depends_on"], ["grounding"])
        self.assertIn("content-grounder", grounding_stage["agents"])
        self.assertIn("content-grounder", contracts["agents"])
        self.assertIn("chapter-realizer-*", drafting_stage["agents"])
        self.assertIn("chapter-realizer-*", contracts["agents"])
        self.assertIn("chapter-expander-*", contracts["agents"])
        self.assertTrue(any("扩写深化" in item for item in contracts["agents"]["chapter-realizer-*"]["must_not"]))

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

    def test_scoring_applicability_v2_allows_confirmed_group_composition(self):
        applicability = self.valid_scoring_applicability_v2()
        scoring_map = {
            "selected_scoring_group_ids": ["SCG-GLOBAL", "SCG-6-1"],
            "items": [
                {
                    "scoring_item_id": "SCI-6-1-01",
                    "scoring_group_id": "SCG-6-1",
                    "source_segment_id": "SEG-6-1",
                }
            ],
        }

        report = bidflow.validate_scoring_applicability(applicability, "6-1", scoring_map)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["selected_group_count"], 2)

    def test_scoring_applicability_v2_blocks_cross_package_scoring_item(self):
        applicability = self.valid_scoring_applicability_v2()
        scoring_map = {
            "items": [
                {
                    "scoring_item_id": "SCI-OTHER-01",
                    "scoring_group_id": "SCG-OTHER",
                    "source_segment_id": "SEG-OTHER",
                }
            ]
        }

        report = bidflow.validate_scoring_applicability(applicability, "6-1", scoring_map)

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("未选中或已排除评分组" in item["message"] for item in report["findings"]))

    def test_scoring_applicability_v2_blocks_selected_superseded_group(self):
        applicability = self.valid_scoring_applicability_v2()
        applicability["scoring_groups"][0]["superseded_by_group_ids"] = ["SCG-6-1"]

        report = bidflow.validate_scoring_applicability(applicability, "6-1")

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("已被选中评分组覆盖" in item["message"] for item in report["findings"]))

    def test_response_register_accepts_source_to_bidder_transformation(self):
        report = bidflow.validate_response_register(self.valid_response_register())

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["confirmed_count"], 1)

    def test_response_register_blocks_purchaser_duty_as_direct_commitment(self):
        register = self.valid_response_register()
        record = register["records"][0]
        record["record_type"] = "PURCHASER_OBLIGATION"
        record["source_requirement"]["source_actor"] = "PURCHASER"

        report = bidflow.validate_response_register(register)

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("采购方义务" in item["message"] for item in report["findings"]))

    def test_response_content_preserves_confirmed_scope_and_blocks_expansion(self):
        register = self.valid_response_register()
        task = {"response_item_ids": ["RSP-0001"]}
        evidence = {
            "response_item_ids": ["RSP-0001"],
            "supported_claims": [
                {
                    "claim_text": "我司将在集中评审阶段安排不少于1人负责现场联络。",
                    "response_item_ids": ["RSP-0001"],
                    "source_refs": ["SRC-SPEC"],
                }
            ],
        }
        valid_content = "我司将在集中评审阶段安排不少于1人负责现场联络。联络事项同步登记并跟踪反馈。"
        formatted_content = "我司将在**集中评审阶段**安排不少于 1 人负责现场联络；联络事项同步登记并跟踪反馈。"
        invalid_content = valid_content + "我司同时提供全周期驻场服务。"

        valid_report = bidflow.validate_response_content(register, valid_content, task, evidence)
        formatted_report = bidflow.validate_response_content(register, formatted_content, task, evidence)
        invalid_report = bidflow.validate_response_content(register, invalid_content, task, evidence)

        self.assertEqual(valid_report["status"], "PASS")
        self.assertEqual(formatted_report["status"], "PASS")
        self.assertEqual(invalid_report["status"], "REJECT")
        self.assertTrue(any("禁止扩展" in item["message"] for item in invalid_report["findings"]))

    def test_response_content_does_not_accept_evidence_as_body_response(self):
        register = self.valid_response_register()
        task = {"response_item_ids": ["RSP-0001"]}
        evidence = {
            "response_item_ids": ["RSP-0001"],
            "supported_claims": [
                {
                    "claim_text": "我司将在集中评审阶段安排不少于1人负责现场联络。",
                    "response_item_ids": ["RSP-0001"],
                    "source_refs": ["SRC-SPEC"],
                }
            ],
        }

        report = bidflow.validate_response_content(register, "联络事项由项目组登记。", task, evidence)

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("evidence 不能替代正文响应" in item["message"] for item in report["findings"]))

    def test_grounding_pack_must_match_central_response_register(self):
        register = self.valid_response_register()
        record = register["records"][0]
        grounding = self.valid_grounding_pack()
        grounding.update(
            {
                "version": 2,
                "allowed_scoring_group_ids": ["SCG-6-1"],
                "response_refs": [
                    {
                        "response_item_id": "RSP-0001",
                        "requirement_id": "REQ-0001",
                        "response_mode": "DIRECT_COMMITMENT",
                        "canonical_response": record["canonical_response"],
                        "fixed_elements": record["fixed_elements"],
                        "allowed_expansion": record["allowed_expansion"],
                        "forbidden_changes": record["forbidden_changes"],
                        "source_refs": ["SRC-SPEC"],
                    }
                ],
            }
        )

        valid_report = bidflow.validate_grounding_pack(
            grounding,
            register,
            self.valid_scoring_applicability_v2(),
        )
        grounding["response_refs"][0]["canonical_response"] = "我司安排人员联络。"
        invalid_report = bidflow.validate_grounding_pack(
            grounding,
            register,
            self.valid_scoring_applicability_v2(),
        )

        self.assertEqual(valid_report["status"], "PASS")
        self.assertEqual(invalid_report["status"], "REJECT")
        self.assertTrue(any("擅自改变 canonical_response" in item["message"] for item in invalid_report["findings"]))

    def test_paragraph_plan_must_preserve_grounded_response_elements(self):
        register = self.valid_response_register()
        record = register["records"][0]
        grounding = self.valid_grounding_pack()
        grounding["response_refs"] = [
            {
                "response_item_id": "RSP-0001",
                "canonical_response": record["canonical_response"],
                "fixed_elements": record["fixed_elements"],
            }
        ]
        paragraph_plan = self.valid_paragraph_plan()
        paragraph_plan["version"] = 2
        paragraph = paragraph_plan["paragraphs"][0]
        paragraph["response_item_ids"] = ["RSP-0001"]
        paragraph["canonical_response_refs"] = [
            {"response_item_id": "RSP-0001", "canonical_response": record["canonical_response"]}
        ]
        paragraph["fixed_response_elements"] = [
            {"response_item_id": "RSP-0001", "elements": record["fixed_elements"]}
        ]

        valid_report = bidflow.validate_paragraph_plan(paragraph_plan, grounding)
        paragraph["fixed_response_elements"][0]["elements"] = ["现场联络"]
        invalid_report = bidflow.validate_paragraph_plan(paragraph_plan, grounding)

        self.assertEqual(valid_report["status"], "PASS")
        self.assertEqual(invalid_report["status"], "REJECT")
        self.assertTrue(any("fixed_response_elements 与章节依据包不一致" in item["message"] for item in invalid_report["findings"]))

    def test_chapter_plan_blocks_response_requirement_mismatch(self):
        plan = self.valid_chapter_plan()
        plan["version"] = 2
        plan["response_item_mappings"] = [
            {
                "response_item_id": "RSP-0001",
                "requirement_id": "REQ-9999",
                "primary_section_id": "SEC-001",
                "supporting_section_ids": [],
            }
        ]
        plan["writing_tasks"][0]["response_item_ids"] = ["RSP-0001"]

        report = bidflow.validate_chapter_plan(
            plan,
            self.valid_requirements(),
            self.valid_scoring_map(),
            self.valid_response_register(),
        )

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("requirement_id 与中央响应台账不一致" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_accepts_covered_requirements_and_scoring(self):
        report = bidflow.validate_chapter_plan(
            self.valid_chapter_plan(),
            self.valid_requirements(),
            self.valid_scoring_map(),
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["mapped_requirement_count"], 1)
        self.assertEqual(report["mapped_scoring_item_count"], 1)
        self.assertEqual(report["mapped_score_atom_count"], 1)

    def test_validate_scoring_map_accepts_highest_band_atomic_breakdown(self):
        report = bidflow.validate_scoring_map(self.valid_scoring_map())

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["score_atom_count"], 1)

    def test_validate_scoring_map_blocks_missing_highest_band_atoms(self):
        scoring_map = self.valid_scoring_map()
        scoring_map["items"][0]["score_atoms"] = []

        report = bidflow.validate_scoring_map(scoring_map)

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("尚未拆成 score_atoms" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_reviews_score_atom_title_mismatch(self):
        plan = self.valid_chapter_plan()
        plan["sections"][2]["title"] = "总体技术路线"

        report = bidflow.validate_chapter_plan(plan, self.valid_requirements(), self.valid_scoring_map())

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("未与评分内容对象逐项对应" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_requires_cross_section_response_strategy(self):
        plan = self.valid_chapter_plan()
        atom_mapping = plan["scoring_item_mappings"][0]["score_atom_mappings"][0]
        atom_mapping["supporting_section_ids"] = ["SEC-001-01"]

        report = bidflow.validate_chapter_plan(plan, self.valid_requirements(), self.valid_scoring_map())

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("必须声明概述、深化或差异化响应策略" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_blocks_missing_mandatory_mapping(self):
        plan = self.valid_chapter_plan()
        plan["sections"][0]["mapped_requirement_ids"] = []
        plan["sections"][1]["mapped_requirement_ids"] = []
        plan["sections"][2]["mapped_requirement_ids"] = []
        plan["technical_requirement_mappings"] = []
        plan["writing_tasks"][0]["requirement_ids"] = []

        report = bidflow.validate_chapter_plan(plan, self.valid_requirements(), {})

        self.assertEqual(report["status"], "REJECT")
        self.assertTrue(any("强制/必答原子要点未映射" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_reviews_generic_internal_outline(self):
        plan = self.valid_chapter_plan()
        plan["sections"] = plan["sections"][:1]
        plan["scoring_item_mappings"][0].pop("mapped_section_hierarchy")

        report = bidflow.validate_chapter_plan(
            plan,
            self.valid_requirements(),
            {"items": [{"scoring_item_id": "SCI-001"}]},
        )

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("缺少二级及以下标题承接" in item["message"] for item in report["findings"]))

    def test_validate_chapter_plan_blocks_more_than_five_sibling_subsections(self):
        plan = self.valid_chapter_plan()
        for index in range(6):
            plan["sections"].append(
                {
                    "section_id": f"SEC-001-01-X{index}",
                    "level": 3,
                    "title": f"子标题{index}",
                    "order": 10 + index,
                    "parent_section_id": "SEC-001-01",
                    "hierarchy_role": "scoring_description_breakdown",
                    "derived_from": "score_description",
                    "scoring_derivation": {
                        "scoring_item_id": "SCI-001",
                        "score_description_excerpt": "服务方案结构清晰、内容完整",
                        "decomposition_keywords": ["内容完整"],
                    },
                    "mapped_scoring_item_ids": ["SCI-001"],
                    "mapped_requirement_ids": ["REQ-0001"],
                    "writing_task_ids": ["TASK-001"],
                }
            )

        report = bidflow.validate_chapter_plan(
            plan,
            self.valid_requirements(),
            {"items": [{"scoring_item_id": "SCI-001"}]},
        )

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("超过最多 5 个" in item["message"] for item in report["findings"]))

    def test_validate_chapter_draft_accepts_realized_outline_and_evidence(self):
        draft = (
            "# 实施方案\n\n"
            "我司依据 REQ-0001 和 SCI-001 组织实施方案编制，围绕资料核查、问题记录和反馈闭环落实服务内容，"
            "形成问题清单和实施记录，使章节初稿对应服务方案结构要求。\n\n"
            "## 服务方案结构\n\n"
            "我司按资料完整性和问题闭环设置控制节点，通过核查、记录、反馈等动作推进成果提交，并保留来源引用。"
        )
        evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "paragraph_id": "P001",
                    "paragraph_plan_ids": ["PP-001"],
                    "requirement_ids": ["REQ-0001"],
                    "scoring_item_ids": ["SCI-001"],
                    "source_refs": [{"source_id": "SRC-001", "file": "招标文件.pdf"}],
                }
            ]
        }

        report = bidflow.validate_chapter_draft(
            self.valid_chapter_task(),
            draft,
            evidence,
            self.valid_grounding_pack(),
            self.valid_paragraph_plan(),
        )

        self.assertEqual(report["status"], "PASS")

    def test_collect_ids_does_not_treat_unrelated_list_values_as_ids(self):
        paragraph_plan = self.valid_paragraph_plan()

        ids = bidflow.collect_ids(paragraph_plan, ("paragraph_plan_id", "paragraph_plan_ids"))

        self.assertEqual(ids, {"PP-001"})

    def test_validate_grounding_pack_accepts_real_project_basis(self):
        report = bidflow.validate_grounding_pack(self.valid_grounding_pack())

        self.assertEqual(report["status"], "PASS")

    def test_validate_paragraph_plan_accepts_actions_controls_and_deliverables(self):
        report = bidflow.validate_paragraph_plan(self.valid_paragraph_plan(), self.valid_grounding_pack())

        self.assertEqual(report["status"], "PASS")

    def test_validate_paragraph_plan_flags_missing_score_atom(self):
        paragraph_plan = self.valid_paragraph_plan()
        paragraph_plan["paragraphs"][0]["score_atom_ids"] = []

        report = bidflow.validate_paragraph_plan(paragraph_plan, self.valid_grounding_pack())

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("评分内容对象未进入段落计划" in item["message"] for item in report["findings"]))

    def test_validate_chapter_draft_accepts_grounded_realization(self):
        draft = (
            "# 实施方案\n\n"
            "我司依据 REQ-0001、SCI-001 和 REJ-001 组织实施方案编制，围绕资料核查、问题记录和反馈闭环开展服务内容响应，"
            "形成问题清单和实施记录，确保服务内容完整性能够对应本项目实施方案要求。\n\n"
            "## 服务方案结构\n\n"
            "我司围绕资料完整性、问题闭环和成果提交建立执行安排，通过核查、记录、反馈等动作支撑章节初稿真实落位。"
        )
        evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "paragraph_id": "P001",
                    "paragraph_plan_ids": ["PP-001"],
                    "requirement_ids": ["REQ-0001"],
                    "scoring_item_ids": ["SCI-001"],
                    "rejection_clause_ids": ["REJ-001"],
                    "source_refs": [{"source_id": "SRC-TENDER", "file": "招标文件.pdf"}],
                }
            ]
        }

        report = bidflow.validate_chapter_draft(
            self.valid_chapter_task(),
            draft,
            evidence,
            self.valid_grounding_pack(),
            self.valid_paragraph_plan(),
        )

        self.assertEqual(report["status"], "PASS")

    def test_validate_chapter_draft_flags_forbidden_connector(self):
        draft = "# 实施方案\n\n首先，我司依据 REQ-0001 和 SCI-001 组织实施方案编制。"
        evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "paragraph_plan_ids": ["PP-001"],
                    "requirement_ids": ["REQ-0001"],
                    "scoring_item_ids": ["SCI-001"],
                    "source_refs": [{"source_id": "SRC-001"}],
                }
            ]
        }

        report = bidflow.validate_chapter_draft(
            self.valid_chapter_task(),
            draft,
            evidence,
            self.valid_grounding_pack(),
            self.valid_paragraph_plan(),
        )

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("禁用连接词" in item["message"] for item in report["findings"]))

    def test_validate_rejection_content_flags_risky_phrase(self):
        report = bidflow.validate_rejection_content(
            self.valid_rejection_clauses(),
            "本章节提供备选方案。",
            self.valid_chapter_task(),
        )

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("废标/否决风险" in item["message"] for item in report["findings"]))

    def test_validate_rejection_content_allows_explicit_risk_avoidance(self):
        evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "rejection_clause_ids": ["REJ-001"],
                    "source_refs": [{"source_id": "SRC-TENDER"}],
                }
            ],
        }

        report = bidflow.validate_rejection_content(
            self.valid_rejection_clauses(),
            "我司确保不存在实质性不响应，不提供备选方案。",
            self.valid_chapter_task(),
            evidence,
        )

        self.assertEqual(report["status"], "PASS")

    def test_unconfirmed_claim_requires_claim_level_source(self):
        generic_evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "supported_claims": [{"claim_text": "招标文件要求两小时响应", "source_refs": []}],
                    "source_refs": [{"source_id": "SRC-TENDER"}],
                }
            ],
        }

        findings = bidflow.unconfirmed_claim_findings("我司承诺两小时响应。", generic_evidence)

        self.assertTrue(any("无来源强事实或承诺" in item["message"] for item in findings))

    def test_unconfirmed_claim_accepts_claim_level_source(self):
        claim_evidence = {
            "task_id": "TASK-001",
            "paragraphs": [
                {
                    "supported_claims": [
                        {
                            "claim_text": "招标文件要求两小时响应",
                            "source_refs": [{"source_id": "SRC-TENDER"}],
                        }
                    ]
                }
            ],
        }

        findings = bidflow.unconfirmed_claim_findings("我司按要求两小时响应。", claim_evidence)

        self.assertEqual(findings, [])

    def test_validate_chapter_draft_flags_missing_outline_title(self):
        draft = "# 实施方案\n\n我司依据 REQ-0001 和 SCI-001 组织实施方案编制。"
        evidence = {
            "paragraphs": [
                {
                    "requirement_ids": ["REQ-0001"],
                    "scoring_item_ids": ["SCI-001"],
                    "source_refs": [{"source_id": "SRC-001"}],
                }
            ]
        }

        report = bidflow.validate_chapter_draft(self.valid_chapter_task(), draft, evidence)

        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("初稿缺少规划标题" in item["message"] for item in report["findings"]))

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
                        "scoring_map": self.valid_scoring_map(),
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

    def test_validate_task_pipeline_rechecks_report_status(self):
        with tempfile.TemporaryDirectory() as temp:
            project_dir = Path(temp)
            for directory in ("tasks", "grounding", "paragraph-plans", "chapters", "evidence", "reviews"):
                (project_dir / directory).mkdir(parents=True, exist_ok=True)

            task = self.valid_chapter_task()
            task.update(
                {
                    "output_file": "chapters/implementation.md",
                    "evidence_file": "evidence/implementation.json",
                    "draft_review_file": "reviews/chapter-draft-implementation.json",
                }
            )
            bidflow.write_json(project_dir / "tasks" / "chapter-task-001.json", task)
            bidflow.write_json(project_dir / "grounding" / "implementation.json", self.valid_grounding_pack())
            bidflow.write_json(project_dir / "paragraph-plans" / "implementation.json", self.valid_paragraph_plan())
            (project_dir / "chapters" / "implementation.md").write_text(
                "# 实施方案\n\n我司依据 REQ-0001、SCI-001 和 REJ-001 围绕资料核查、问题记录和反馈闭环开展服务，形成问题清单和实施记录。\n\n"
                "## 服务方案结构\n\n我司按资料完整性和问题闭环设置控制节点，通过核查、记录、反馈推进成果提交。",
                encoding="utf-8",
            )
            bidflow.write_json(
                project_dir / "evidence" / "implementation.json",
                {
                    "task_id": "TASK-001",
                    "paragraphs": [
                        {
                            "paragraph_id": "P001",
                            "paragraph_plan_ids": ["PP-001"],
                            "requirement_ids": ["REQ-0001"],
                            "scoring_item_ids": ["SCI-001"],
                            "rejection_clause_ids": ["REJ-001"],
                            "source_refs": [{"source_id": "SRC-TENDER"}],
                        }
                    ],
                },
            )
            bidflow.write_json(
                project_dir / "reviews" / "chapter-draft-implementation.json",
                {"status": "REVIEW_REQUIRED", "findings": []},
            )

            errors = bidflow.validate_task_pipeline(project_dir, "drafting", self.valid_rejection_clauses())

            self.assertTrue(any("chapter-draft-implementation.json 状态为 REVIEW_REQUIRED" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
