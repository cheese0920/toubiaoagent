from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_TEMPLATE = ROOT / "templates" / "project.json"
WORKFLOW = ROOT / "config" / "workflow.json"
AGENT_CONTRACTS = ROOT / "config" / "agent-contracts.json"
MINIMALISM_ROUTER = ROOT / "config" / "minimalism-router.json"
WORKFLOW_STATE_TEMPLATE = ROOT / "templates" / "workflow-state.json"
SUMMARY_OPENINGS = (
    "总体而言",
    "总体来看",
    "总的来说",
    "概括而言",
    "简而言之",
    "综上",
    "综上所述",
    "由此可见",
    "可以看出",
)
SUMMARY_ENDINGS = (
    "综上。",
    "综上所述。",
    "总之。",
    "由此可见。",
    "因此可见。",
    "可以看出。",
    "具有重要意义。",
    "提供有力保障。",
    "奠定坚实基础。",
)
FORBIDDEN_CONNECTORS = (
    "首先",
    "其次",
    "再次",
    "此外",
    "另外",
    "最后",
    "综上",
    "综上所述",
    "总之",
    "由此可见",
    "可以看出",
)
EMPTY_RHETORIC_PHRASES = (
    "全面",
    "科学",
    "合理",
    "有效",
    "强有力",
    "坚实",
    "完善",
    "优化",
    "提升",
    "保障",
)
CONCRETE_ACTION_HINTS = (
    "核查",
    "评审",
    "复核",
    "记录",
    "反馈",
    "整改",
    "闭环",
    "归档",
    "提交",
    "组织",
    "登记",
    "分派",
    "确认",
    "校审",
    "跟踪",
)
DELIVERABLE_HINTS = (
    "清单",
    "报告",
    "纪要",
    "意见",
    "记录",
    "台账",
    "成果",
    "材料",
    "文件",
)
UNCONFIRMED_CLAIM_PATTERNS = (
    "小时",
    "工作日",
    "自然日",
    "驻场",
    "免费",
    "专家",
    "资质",
    "证书",
    "业绩",
    "接口",
    "系统功能",
)
REJECTION_RISK_PHRASES = (
    "负偏差",
    "负偏离",
    "不响应",
    "无法满足",
    "不能满足",
    "另行收费",
    "另行协商",
    "备选方案",
    "替代方案",
    "不承担",
    "除外",
)
SAFE_REJECTION_CONTEXTS = (
    "无",
    "不存在",
    "不得",
    "避免",
    "防止",
    "杜绝",
    "严禁",
    "消除",
    "不形成",
    "不提供",
    "不采用",
    "不设置",
)
UNRESOLVED_PLACEHOLDERS = (
    "待人工确认",
    "待确认",
    "待补充",
    "待补",
    "TBD",
)
SCORING_GROUP_TYPES = {
    "GLOBAL_COMMON",
    "PACKAGE_COMMON",
    "PACKAGE_SPECIFIC",
    "ADDENDUM_OVERRIDE",
}
SCORING_SELECTION_STATUSES = {"CANDIDATE", "SELECTED", "EXCLUDED", "CONFLICT"}
RESPONSE_RECORD_TYPES = {
    "SUPPLIER_OBLIGATION",
    "PURCHASER_OBLIGATION",
    "PROHIBITION",
    "SCORING_EXPECTATION",
    "CONTRACT_CONDITION",
}
RESPONSE_MODES = {
    "DIRECT_COMMITMENT",
    "COOPERATIVE_ACKNOWLEDGEMENT",
    "PROHIBITION_ACKNOWLEDGEMENT",
    "PLAN_RESPONSE",
    "NO_DRAFT",
}
RESPONSE_STATUSES = {"CONFIRMED", "PENDING", "NEEDS_CONFIRMATION", "CONFLICT", "PROHIBITED"}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def slugify(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "-", name).strip().strip(".")
    return cleaned or "unnamed-project"


def markdown_blocks(text: str) -> list[str]:
    normalized = text.lstrip("\ufeff")
    return [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]


def is_heading(block: str) -> bool:
    return bool(re.fullmatch(r"#{1,6}\s+.+", block))


def effective_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def normalize_label(value: object) -> str:
    return re.sub(r"[\s:：_\-—–（）()【】\[\]、，,。.;；]+", "", str(value or "")).lower()


def boundary_contains(haystack: object, needle: object) -> bool:
    raw_haystack = str(haystack or "").lower()
    raw_needle = str(needle or "").strip().lower()
    if not raw_needle:
        return False
    pattern = rf"(?<![0-9a-z]){re.escape(raw_needle)}(?![0-9a-z])"
    return bool(re.search(pattern, raw_haystack))


def label_matches(target: str, candidates: list[object]) -> bool:
    normalized_target = normalize_label(target)
    if not normalized_target:
        return True
    for candidate in candidates:
        normalized_candidate = normalize_label(candidate)
        if not normalized_candidate:
            continue
        if normalized_target == normalized_candidate:
            return True
        if boundary_contains(candidate, target) or boundary_contains(target, candidate):
            return True
        if min(len(normalized_target), len(normalized_candidate)) >= 8 and (
            normalized_target in normalized_candidate or normalized_candidate in normalized_target
        ):
            return True
    return False


def is_positive(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().upper() in {"TRUE", "YES", "Y", "DONE", "READABLE", "FULL", "PARTIAL"}


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def try_import(module_name: str) -> Any | None:
    try:
        module = __import__(module_name)
    except ImportError:
        return None
    return module


def normalize_source_type(value: str) -> str:
    normalized = normalize_label(value).replace("technicalspecification", "technical_specification")
    aliases = {
        "tender": "tender",
        "招标文件": "tender",
        "technical_specification": "technical_specification",
        "technicalspecification": "technical_specification",
        "技术规范书": "technical_specification",
        "historicalreference": "historical_reference",
        "historical_reference": "historical_reference",
        "历史参考": "historical_reference",
        "supportingmaterial": "supporting_material",
        "supporting_material": "supporting_material",
        "支撑材料": "supporting_material",
        "technicalscoring": "technical_scoring",
        "scoringrules": "scoring_rules",
        "formatrules": "format_rules",
        "technicalbidformat": "technical_bid_format",
    }
    return aliases.get(normalized, normalized or "supporting_material")


def infer_source_type(path: Path, project_dir: Path) -> str:
    try:
        parts = [part.lower() for part in path.relative_to(project_dir).parts]
    except ValueError:
        parts = [part.lower() for part in path.parts]
    joined = "/".join(parts)
    if "technical-specification" in joined or "technical_specification" in joined:
        return "technical_specification"
    if "historical-reference" in joined or "historical_reference" in joined:
        return "historical_reference"
    if "supporting-material" in joined or "supporting_material" in joined:
        return "supporting_material"
    if "technical-scoring" in joined or "scoring" in joined:
        return "technical_scoring"
    if "format" in joined:
        return "format_rules"
    if "tender" in joined:
        return "tender"
    return "supporting_material"


def source_role_for_type(source_type: str) -> str:
    return "core" if source_type in {
        "tender",
        "technical_specification",
        "technical_scoring",
        "scoring_rules",
        "technical_bid_format",
        "format_rules",
    } else "reference"


def source_group_for_type(source_type: str) -> str:
    if source_type == "technical_specification":
        return "technical_specification"
    if source_type == "tender":
        return "tender"
    if source_type == "historical_reference":
        return "historical_reference"
    return "supporting_material"


def heading_level(text: str) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    patterns = [
        (1, r"^(第[一二三四五六七八九十百]+[章节篇部分])"),
        (1, r"^[一二三四五六七八九十]+[、.．]\s*"),
        (2, r"^（[一二三四五六七八九十]+）"),
        (2, r"^\([一二三四五六七八九十]+\)"),
        (2, r"^\d+[、.．]\s*"),
        (3, r"^\d+\.\d+"),
    ]
    for level, pattern in patterns:
        if re.match(pattern, stripped):
            return level
    if len(stripped) <= 40 and not re.search(r"[。！？!?；;]$", stripped):
        return 2
    return None


def validate_expansion(
    source: str,
    expanded: str,
    evidence: object | None = None,
    paragraph_plan: dict | None = None,
) -> dict:
    source_blocks = markdown_blocks(source)
    expanded_blocks = markdown_blocks(expanded)
    findings: list[str] = []

    if len(source_blocks) != len(expanded_blocks):
        findings.append(
            f"分段数量不一致：原文 {len(source_blocks)} 段，扩写稿 {len(expanded_blocks)} 段"
        )

    source_headings = [block for block in source_blocks if is_heading(block)]
    expanded_headings = [block for block in expanded_blocks if is_heading(block)]
    if source_headings != expanded_headings:
        findings.append("标题内容、层级或顺序发生变化")

    paragraph_ratios: list[float] = []
    for index, (original, result) in enumerate(zip(source_blocks, expanded_blocks), start=1):
        if is_heading(original):
            if original != result:
                findings.append(f"第 {index} 个块的标题被改动")
            continue
        if is_heading(result):
            findings.append(f"第 {index} 个正文段落被替换为标题")
            continue

        original_length = max(effective_length(original), 1)
        ratio = effective_length(result) / original_length
        paragraph_ratios.append(round(ratio, 2))
        if ratio < 2.5:
            findings.append(f"第 {index} 个正文段落扩写比例不足：{ratio:.2f}")

        normalized = re.sub(r"^[（(]?\d+[）).、]?\s*", "", result.strip())
        if normalized.startswith(SUMMARY_OPENINGS):
            findings.append(f"第 {index} 个正文段落使用总结式段首")
        if normalized.endswith(SUMMARY_ENDINGS):
            findings.append(f"第 {index} 个正文段落使用总结式段尾")

    source_length = max(effective_length(source), 1)
    total_ratio = effective_length(expanded) / source_length
    if not 2.7 <= total_ratio <= 3.5:
        findings.append(f"全文扩写比例应在 2.7 至 3.5 之间，实际为 {total_ratio:.2f}")

    for item in forbidden_phrase_findings(expanded):
        findings.append(item["message"])
    for item in generic_rhetoric_findings(expanded):
        findings.append(item["message"])
    for item in unconfirmed_claim_findings(expanded, evidence, source):
        findings.append(item["message"])
    for item in rejection_risk_findings(expanded):
        findings.append(item["message"])
    keywords = plan_keywords(paragraph_plan, None)
    if keywords:
        matched_keywords = [keyword for keyword in keywords if keyword in expanded]
        if len(matched_keywords) < min(3, len(keywords)):
            findings.append("扩写稿未充分体现段落计划中的项目关键词、动作或交付物")

    return {
        "status": "PASS" if not findings else "REVIEW_REQUIRED",
        "total_length_ratio": round(total_ratio, 2),
        "paragraph_length_ratios": paragraph_ratios,
        "structure_matches": len(source_blocks) == len(expanded_blocks) and source_headings == expanded_headings,
        "findings": findings,
    }


def markdown_heading_titles(text: str) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip())
        if match:
            titles.append(match.group(1).strip())
    return titles


def collect_ids(values: object, id_keys: tuple[str, ...]) -> set[str]:
    found: set[str] = set()

    def walk(value: object, allow_scalar: bool) -> None:
        if isinstance(value, str):
            if allow_scalar and value.strip():
                found.add(value.strip())
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if allow_scalar or key in id_keys:
                    walk(child, True)
                elif isinstance(child, (dict, list)):
                    walk(child, False)
            return
        if isinstance(value, list):
            for child in value:
                walk(child, allow_scalar)

    direct_scalar_collection = isinstance(values, str) or (
        isinstance(values, list) and all(not isinstance(item, (dict, list)) for item in values)
    )
    walk(values, direct_scalar_collection)
    return found


def collect_text_values(values: object, keys: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if isinstance(values, dict):
        for key, value in values.items():
            if key in keys:
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                elif isinstance(value, list):
                    found.extend(str(item).strip() for item in value if str(item).strip())
            elif isinstance(value, (dict, list)):
                found.extend(collect_text_values(value, keys))
    elif isinstance(values, list):
        for value in values:
            found.extend(collect_text_values(value, keys))
    return found


def forbidden_phrase_findings(text: str, phrases: tuple[str, ...] | list[str] = FORBIDDEN_CONNECTORS) -> list[dict]:
    return [
        {"severity": "MAJOR", "message": f"正文出现禁用连接词：{phrase}"}
        for phrase in phrases
        if phrase and phrase in text
    ]


def generic_rhetoric_findings(text: str) -> list[dict]:
    findings: list[dict] = []
    rhetoric_count = sum(text.count(phrase) for phrase in EMPTY_RHETORIC_PHRASES)
    action_count = sum(text.count(phrase) for phrase in CONCRETE_ACTION_HINTS)
    deliverable_count = sum(text.count(phrase) for phrase in DELIVERABLE_HINTS)
    if rhetoric_count >= 6 and action_count < 3:
        findings.append({"severity": "MAJOR", "message": "正文空泛修饰词偏多，但具体执行动作不足"})
    if effective_length(text) >= 300 and deliverable_count == 0:
        findings.append({"severity": "MAJOR", "message": "正文缺少清单、报告、记录、成果等可验证交付物表述"})
    return findings


def evidence_supports_claim(evidence: object | None, phrase: str) -> bool:
    if evidence is None:
        return False
    if isinstance(evidence, dict):
        claim_fields = ("claim", "claim_text", "supported_claim", "supported_claims", "text")
        claim_texts: list[str] = []
        for key in claim_fields:
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                claim_texts.append(value.strip())
            elif isinstance(value, list):
                claim_texts.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
        if any(phrase in claim for claim in claim_texts):
            return bool(collect_ids(evidence, ("source_ref", "source_refs", "source_id", "file")))
        return any(evidence_supports_claim(value, phrase) for value in evidence.values() if isinstance(value, (dict, list)))
    if isinstance(evidence, list):
        return any(evidence_supports_claim(item, phrase) for item in evidence)
    return False


def unconfirmed_claim_findings(text: str, evidence: object | None, source_text: str = "") -> list[dict]:
    findings: list[dict] = []
    for phrase in UNCONFIRMED_CLAIM_PATTERNS:
        if phrase not in text or phrase in source_text or "待人工确认" in text:
            continue
        if not evidence_supports_claim(evidence, phrase):
            findings.append({"severity": "MAJOR", "message": f"疑似出现无来源强事实或承诺：{phrase}"})
    return findings


def rejection_risk_findings(text: str) -> list[dict]:
    findings: list[dict] = []
    for phrase in REJECTION_RISK_PHRASES:
        search_start = 0
        while True:
            position = text.find(phrase, search_start)
            if position < 0:
                break
            prefix = text[max(0, position - 10):position]
            if not any(context in prefix for context in SAFE_REJECTION_CONTEXTS):
                findings.append({"severity": "CRITICAL", "message": f"疑似触发废标/否决风险表述：{phrase}"})
                break
            search_start = position + len(phrase)
    return findings


def plan_keywords(paragraph_plan: dict | None, grounding_pack: dict | None) -> set[str]:
    keywords: set[str] = set()
    if paragraph_plan:
        for key in ("project_keywords", "scoring_keywords", "required_actions", "control_points", "deliverables"):
            keywords.update(collect_text_values(paragraph_plan, (key,)))
    if grounding_pack:
        for key in ("project_keywords", "response_object", "response_objects", "required_actions", "deliverables"):
            keywords.update(collect_text_values(grounding_pack, (key,)))
    return {item for item in keywords if item}


def validate_grounding_pack(
    data: dict,
    response_register: dict | None = None,
    scoring_applicability: dict | None = None,
) -> dict:
    findings: list[dict] = []
    task_id = str(data.get("task_id", "")).strip()
    if not task_id:
        findings.append({"severity": "BLOCKER", "message": "章节依据包缺少 task_id"})
    if not data.get("target_section_ids"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包缺少 target_section_ids"})
    if not data.get("planned_outline_refs"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包缺少 planned_outline_refs"})
    if not data.get("scoring_refs") and not data.get("score_atom_refs"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包缺少评分项或评分内容对象依据"})
    if parse_int(data.get("version"), 1) >= 2 and not data.get("allowed_scoring_group_ids"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包缺少 allowed_scoring_group_ids，无法隔离评分组"})
    if not data.get("technical_requirement_refs") and not data.get("project_facts"):
        findings.append({"severity": "MAJOR", "message": "章节依据包缺少技术规范或项目事实依据"})
    if parse_int(data.get("version"), 1) >= 2 and data.get("technical_requirement_refs") and not data.get("response_refs"):
        findings.append({"severity": "BLOCKER", "message": "章节依据包含技术要求但缺少已确认的 response_refs"})
    if not data.get("source_refs"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包缺少来源引用 source_refs"})
    if not data.get("knowledge_cards"):
        findings.append({"severity": "MAJOR", "message": "章节依据包未声明可复用知识卡"})
    if not data.get("forbidden_claims"):
        findings.append({"severity": "MAJOR", "message": "章节依据包缺少禁用承诺清单"})
    if not data.get("rejection_clause_ids") and not data.get("rejection_scope_confirmed"):
        findings.append({"severity": "MAJOR", "message": "章节依据包未绑定废标/否决条款检查范围"})
    if data.get("open_questions"):
        findings.append({"severity": "CRITICAL", "message": "章节依据包仍有未关闭的 open_questions，禁止进入初稿生成"})

    source_ids = collect_ids(data.get("source_refs", []), ("source_id",))
    for index, fact in enumerate(data.get("project_facts", []), start=1):
        if not isinstance(fact, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个 project_fact 不是对象"})
            continue
        source_ref = str(fact.get("source_ref", "")).strip()
        if not str(fact.get("fact", "")).strip():
            findings.append({"severity": "MAJOR", "message": f"第 {index} 个 project_fact 缺少事实内容"})
        if not source_ref:
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个 project_fact 缺少 source_ref"})
        elif source_ids and source_ref not in source_ids:
            findings.append({"severity": "MAJOR", "message": f"project_fact 引用了未登记来源：{source_ref}"})

    for index, requirement in enumerate(data.get("technical_requirement_refs", []), start=1):
        if not isinstance(requirement, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个 technical_requirement_ref 不是对象"})
            continue
        source_ref = str(requirement.get("source_ref", "")).strip()
        if not source_ref:
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个 technical_requirement_ref 缺少 source_ref"})
        elif source_ids and source_ref not in source_ids:
            findings.append({"severity": "MAJOR", "message": f"technical_requirement_ref 引用了未登记来源：{source_ref}"})

    for index, response in enumerate(data.get("response_refs", []), start=1):
        if not isinstance(response, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个 response_ref 不是对象"})
            continue
        response_item_id = str(response.get("response_item_id", "")).strip()
        label = response_item_id or f"第 {index} 个 response_ref"
        if not response_item_id:
            findings.append({"severity": "BLOCKER", "message": f"{label} 缺少 response_item_id"})
        if not str(response.get("canonical_response", "")).strip():
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "缺少 canonical_response"})
        if not response.get("fixed_elements"):
            findings.append({"severity": "MAJOR", "response_item_id": label, "message": "缺少 fixed_elements"})
        if not response.get("source_refs"):
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "缺少 source_refs"})

    if scoring_applicability is not None:
        allowed_group_ids = collect_ids(data.get("allowed_scoring_group_ids", []), ("scoring_group_id",))
        selected_group_ids = selected_scoring_group_ids(scoring_applicability)
        unknown_group_ids = allowed_group_ids - selected_group_ids
        if unknown_group_ids:
            findings.append({"severity": "BLOCKER", "message": f"章节依据包引用未选中评分组：{sorted(unknown_group_ids)}"})

    if response_register is not None:
        central_records = {
            str(record.get("response_item_id", "")).strip(): record
            for record in response_register_records(response_register)
            if str(record.get("response_item_id", "")).strip()
        }
        response_refs = {
            str(response.get("response_item_id", "")).strip(): response
            for response in data.get("response_refs", [])
            if isinstance(response, dict) and str(response.get("response_item_id", "")).strip()
        }
        unknown_response_ids = set(response_refs) - set(central_records)
        if unknown_response_ids:
            findings.append({"severity": "BLOCKER", "message": f"章节依据包引用未登记响应口径：{sorted(unknown_response_ids)}"})
        for response_item_id in sorted(set(response_refs) & set(central_records)):
            response_ref = response_refs[response_item_id]
            central = central_records[response_item_id]
            if str(central.get("status", "")).upper() != "CONFIRMED" or not central.get("human_confirmed"):
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "章节依据包引用了未确认响应口径"})
            if str(response_ref.get("canonical_response", "")).strip() != str(central.get("canonical_response", "")).strip():
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "章节依据包擅自改变 canonical_response"})
            for field in ("fixed_elements", "allowed_expansion", "forbidden_changes"):
                grounded_values = response_fixed_texts(response_ref.get(field, []))
                central_values = response_fixed_texts(central.get(field, []))
                if grounded_values != central_values:
                    findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"章节依据包中的 {field} 与中央响应台账不一致"})

    for card in data.get("knowledge_cards", []):
        if not isinstance(card, dict):
            continue
        path = str(card.get("path", "")).replace("\\", "/")
        if "references/" not in path or not path.endswith("knowledge-card.md"):
            findings.append({"severity": "MAJOR", "message": f"知识卡未使用统一 references/knowledge-card.md 路径：{path or '<empty>'}"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "task_id": task_id,
        "finding_count": len(findings),
        "findings": findings,
    }


def validate_paragraph_plan(data: dict, grounding_pack: dict | None = None) -> dict:
    findings: list[dict] = []
    task_id = str(data.get("task_id", "")).strip()
    if not task_id:
        findings.append({"severity": "BLOCKER", "message": "段落写作计划缺少 task_id"})
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        findings.append({"severity": "BLOCKER", "message": "段落写作计划 paragraphs 为空或不存在"})
        paragraphs = []

    seen_ids: set[str] = set()
    if grounding_pack is not None and task_id and str(grounding_pack.get("task_id", "")).strip() != task_id:
        findings.append({"severity": "BLOCKER", "message": "段落写作计划 task_id 与章节依据包不一致"})

    grounding_sections = {
        str(item.get("section_id", "")).strip()
        for item in (grounding_pack or {}).get("planned_outline_refs", [])
        if isinstance(item, dict)
        and parse_int(item.get("level"), 0) >= 3
        and str(item.get("response_role", "primary")).strip() == "primary"
        and str(item.get("section_id", "")).strip()
    }
    if not grounding_sections:
        grounding_sections = {
            str(item).strip()
            for item in (grounding_pack or {}).get("target_section_ids", [])
            if str(item).strip()
        }
    planned_sections: set[str] = set()
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个段落计划不是对象"})
            continue
        paragraph_id = str(paragraph.get("paragraph_plan_id", "")).strip()
        label = paragraph_id or f"第 {index} 个段落计划"
        if not paragraph_id:
            findings.append({"severity": "CRITICAL", "message": f"{label} 缺少 paragraph_plan_id"})
        elif paragraph_id in seen_ids:
            findings.append({"severity": "CRITICAL", "message": f"paragraph_plan_id 重复：{paragraph_id}"})
        seen_ids.add(paragraph_id)

        section_id = str(paragraph.get("section_id", "")).strip()
        if not section_id:
            findings.append({"severity": "CRITICAL", "paragraph_plan_id": label, "message": "缺少 section_id"})
        else:
            planned_sections.add(section_id)
        if not paragraph.get("response_object"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少写作对象 response_object"})
        if not paragraph.get("scoring_item_ids") and not paragraph.get("score_atom_ids"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少评分项或评分内容对象绑定"})
        if parse_int(data.get("version"), 1) >= 2 and paragraph.get("requirement_ids") and not paragraph.get("response_item_ids"):
            findings.append({"severity": "BLOCKER", "paragraph_plan_id": label, "message": "段落绑定了要求但缺少 response_item_ids"})
        paragraph_response_ids = collect_ids(paragraph.get("response_item_ids", []), ("response_item_id",))
        canonical_response_ids = collect_ids(paragraph.get("canonical_response_refs", []), ("response_item_id",))
        if parse_int(data.get("version"), 1) >= 2 and paragraph_response_ids:
            missing_canonical_ids = paragraph_response_ids - canonical_response_ids
            if missing_canonical_ids:
                findings.append({"severity": "BLOCKER", "paragraph_plan_id": label, "message": f"段落计划缺少 canonical_response_refs：{sorted(missing_canonical_ids)}"})
            if not paragraph.get("fixed_response_elements"):
                findings.append({"severity": "BLOCKER", "paragraph_plan_id": label, "message": "段落计划缺少 fixed_response_elements"})
            fixed_response_ids = collect_ids(paragraph.get("fixed_response_elements", []), ("response_item_id",))
            missing_fixed_ids = paragraph_response_ids - fixed_response_ids
            if missing_fixed_ids:
                findings.append({"severity": "BLOCKER", "paragraph_plan_id": label, "message": f"段落计划的 fixed_response_elements 未覆盖响应口径：{sorted(missing_fixed_ids)}"})
        if not paragraph.get("project_actual"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少项目实际 project_actual"})
        elif any(marker in str(paragraph.get("project_actual", "")) for marker in UNRESOLVED_PLACEHOLDERS):
            findings.append({"severity": "CRITICAL", "paragraph_plan_id": label, "message": "project_actual 仍含待确认占位内容"})
        if not paragraph.get("required_actions"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少执行动作 required_actions"})
        if not paragraph.get("control_points"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少控制节点 control_points"})
        if not paragraph.get("deliverables"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少交付成果 deliverables"})
        if not paragraph.get("source_refs"):
            findings.append({"severity": "CRITICAL", "paragraph_plan_id": label, "message": "缺少来源引用 source_refs"})
        if not paragraph.get("forbidden_claims"):
            findings.append({"severity": "MAJOR", "paragraph_plan_id": label, "message": "缺少段落级禁用承诺 forbidden_claims"})

    missing_grounded_sections = grounding_sections - planned_sections
    if missing_grounded_sections:
        findings.append({"severity": "CRITICAL", "message": f"依据包章节未形成段落计划：{sorted(missing_grounded_sections)}"})

    if grounding_pack is not None:
        grounded_atom_ids = collect_ids(grounding_pack.get("score_atom_refs", []), ("score_atom_id",))
        planned_atom_ids = collect_ids(paragraphs, ("score_atom_id", "score_atom_ids"))
        missing_atom_ids = grounded_atom_ids - planned_atom_ids
        if missing_atom_ids:
            findings.append({"severity": "CRITICAL", "message": f"评分内容对象未进入段落计划：{sorted(missing_atom_ids)}"})

        grounded_requirement_ids = collect_ids(
            grounding_pack.get("technical_requirement_refs", []),
            ("requirement_id",),
        )
        planned_requirement_ids = collect_ids(paragraphs, ("requirement_id", "requirement_ids"))
        missing_requirement_ids = grounded_requirement_ids - planned_requirement_ids
        if missing_requirement_ids:
            findings.append({"severity": "CRITICAL", "message": f"技术要求未进入段落计划：{sorted(missing_requirement_ids)}"})

        grounded_response_ids = collect_ids(grounding_pack.get("response_refs", []), ("response_item_id", "response_item_ids"))
        planned_response_ids = collect_ids(paragraphs, ("response_item_id", "response_item_ids"))
        missing_response_ids = grounded_response_ids - planned_response_ids
        if missing_response_ids:
            findings.append({"severity": "BLOCKER", "message": f"已确认响应口径未进入段落计划：{sorted(missing_response_ids)}"})
        grounded_response_by_id = {
            str(item.get("response_item_id", "")).strip(): item
            for item in grounding_pack.get("response_refs", [])
            if isinstance(item, dict) and str(item.get("response_item_id", "")).strip()
        }
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = str(paragraph.get("paragraph_plan_id", "")).strip()
            canonical_by_id = {
                str(item.get("response_item_id", "")).strip(): item
                for item in paragraph.get("canonical_response_refs", [])
                if isinstance(item, dict) and str(item.get("response_item_id", "")).strip()
            }
            fixed_by_id = {
                str(item.get("response_item_id", "")).strip(): item
                for item in paragraph.get("fixed_response_elements", [])
                if isinstance(item, dict) and str(item.get("response_item_id", "")).strip()
            }
            for response_item_id in collect_ids(paragraph.get("response_item_ids", []), ("response_item_id",)):
                grounded_response = grounded_response_by_id.get(response_item_id)
                if grounded_response is None:
                    continue
                canonical_ref = canonical_by_id.get(response_item_id, {})
                if str(canonical_ref.get("canonical_response", "")).strip() != str(grounded_response.get("canonical_response", "")).strip():
                    findings.append({"severity": "BLOCKER", "paragraph_plan_id": paragraph_id, "response_item_id": response_item_id, "message": "段落计划擅自改变 canonical_response"})
                fixed_ref = fixed_by_id.get(response_item_id, {})
                if response_fixed_texts(fixed_ref.get("elements", [])) != response_fixed_texts(grounded_response.get("fixed_elements", [])):
                    findings.append({"severity": "BLOCKER", "paragraph_plan_id": paragraph_id, "response_item_id": response_item_id, "message": "段落计划中的 fixed_response_elements 与章节依据包不一致"})

        grounded_rejection_ids = collect_ids(grounding_pack, ("rejection_clause_id", "rejection_clause_ids"))
        planned_rejection_ids = collect_ids(paragraphs, ("rejection_clause_id", "rejection_clause_ids"))
        missing_rejection_ids = grounded_rejection_ids - planned_rejection_ids
        if missing_rejection_ids:
            findings.append({"severity": "CRITICAL", "message": f"废标/否决条款未进入段落计划：{sorted(missing_rejection_ids)}"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "task_id": task_id,
        "paragraph_count": len(paragraphs),
        "findings": findings,
    }


def validate_rejection_content(rejections: dict, content: str, task: dict | None = None, evidence: object | None = None) -> dict:
    findings: list[dict] = []
    task_clause_ids = collect_ids(task or {}, ("rejection_clause_id", "rejection_clause_ids"))
    content_and_evidence = f"{content}\n{json.dumps(evidence, ensure_ascii=False) if evidence is not None else ''}"
    clauses = rejections.get("clauses", [])
    if not isinstance(clauses, list):
        clauses = []
        findings.append({"severity": "BLOCKER", "message": "废标/否决条款 clauses 必须为数组"})
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        clause_id = str(clause.get("clause_id", "")).strip()
        if not clause_id:
            findings.append({"severity": "CRITICAL", "message": "废标/否决条款缺少 clause_id"})
            continue
        applicable = clause.get("applicable", clause.get("current_package_applicable", True))
        confirmed = clause.get("confirmed", clause.get("applicability_confirmed", True))
        if applicable is False:
            continue
        if confirmed is False:
            findings.append({"severity": "CRITICAL", "clause_id": clause_id, "message": "废标/否决条款适用性未确认"})
        if task_clause_ids and clause_id in task_clause_ids and clause_id not in content_and_evidence:
            findings.append({"severity": "MAJOR", "clause_id": clause_id, "message": "任务绑定的废标/否决条款未在正文或证据中定位"})
    registered_clause_ids = {
        str(clause.get("clause_id", "")).strip()
        for clause in clauses
        if isinstance(clause, dict) and str(clause.get("clause_id", "")).strip()
    }
    missing_clause_ids = task_clause_ids - registered_clause_ids
    if missing_clause_ids:
        findings.append({"severity": "BLOCKER", "message": f"任务引用了未登记的废标/否决条款：{sorted(missing_clause_ids)}"})
    findings.extend(rejection_risk_findings(content))
    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "clause_count": len(clauses),
        "checked_task_clause_count": len(task_clause_ids),
        "findings": findings,
    }


def validate_chapter_evidence(
    evidence: object,
    expected_task_id: str = "",
    paragraph_plan: dict | None = None,
) -> dict:
    findings: list[dict] = []
    if not isinstance(evidence, dict):
        return {
            "status": "REJECT",
            "paragraph_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "evidence 必须为对象"}],
        }

    evidence_task_id = str(evidence.get("task_id", "")).strip()
    if not evidence_task_id:
        findings.append({"severity": "CRITICAL", "message": "evidence 缺少 task_id"})
    elif expected_task_id and evidence_task_id != expected_task_id:
        findings.append({"severity": "BLOCKER", "message": "evidence task_id 与章节任务书不一致"})

    paragraphs = evidence.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        findings.append({"severity": "BLOCKER", "message": "evidence paragraphs 为空或不存在"})
        paragraphs = []

    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, dict):
            findings.append({"severity": "CRITICAL", "message": f"evidence 第 {index} 个段落不是对象"})
            continue
        paragraph_id = str(paragraph.get("paragraph_id", "")).strip() or f"第 {index} 个证据段落"
        if not collect_ids(paragraph, ("source_ref", "source_refs", "source_id", "file")):
            findings.append({"severity": "CRITICAL", "paragraph_id": paragraph_id, "message": "缺少来源引用"})
        for claim in paragraph.get("supported_claims", []):
            if not isinstance(claim, dict):
                findings.append({"severity": "MAJOR", "paragraph_id": paragraph_id, "message": "supported_claim 不是对象"})
                continue
            if not str(claim.get("claim_text", "")).strip():
                findings.append({"severity": "MAJOR", "paragraph_id": paragraph_id, "message": "supported_claim 缺少 claim_text"})
            if not collect_ids(claim, ("source_ref", "source_refs", "source_id", "file")):
                findings.append({"severity": "CRITICAL", "paragraph_id": paragraph_id, "message": "supported_claim 缺少来源引用"})
        paragraph_response_ids = collect_ids(paragraph, ("response_item_id", "response_item_ids"))
        claim_response_ids = collect_ids(paragraph.get("supported_claims", []), ("response_item_id", "response_item_ids"))
        if parse_int(evidence.get("version"), 1) >= 2 and paragraph_response_ids - claim_response_ids:
            findings.append({"severity": "CRITICAL", "paragraph_id": paragraph_id, "message": f"supported_claims 未覆盖段落响应口径：{sorted(paragraph_response_ids - claim_response_ids)}"})

    if evidence.get("unresolved_claims"):
        findings.append({"severity": "CRITICAL", "message": "evidence 仍有 unresolved_claims，禁止章节通过"})

    if paragraph_plan is not None:
        expected_plan_ids = collect_ids(paragraph_plan, ("paragraph_plan_id",))
        located_plan_ids = collect_ids(paragraphs, ("paragraph_plan_id", "paragraph_plan_ids"))
        missing_plan_ids = expected_plan_ids - located_plan_ids
        if missing_plan_ids:
            findings.append({"severity": "CRITICAL", "message": f"evidence 未覆盖段落计划：{sorted(missing_plan_ids)}"})
        expected_response_ids = collect_ids(paragraph_plan, ("response_item_id", "response_item_ids"))
        located_response_ids = collect_ids(paragraphs, ("response_item_id", "response_item_ids"))
        missing_response_ids = expected_response_ids - located_response_ids
        if missing_response_ids:
            findings.append({"severity": "BLOCKER", "message": f"evidence 未覆盖响应口径：{sorted(missing_response_ids)}"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "paragraph_count": len(paragraphs),
        "findings": findings,
    }


def validate_chapter_draft(
    task: dict,
    draft: str,
    evidence: object | None = None,
    grounding_pack: dict | None = None,
    paragraph_plan: dict | None = None,
) -> dict:
    findings: list[dict] = []
    outline = task.get("planned_outline", [])
    if not isinstance(outline, list) or not outline:
        findings.append({"severity": "BLOCKER", "message": "章节任务书缺少 planned_outline"})
        outline = []

    headings = markdown_heading_titles(draft)
    normalized_headings = [normalize_label(title) for title in headings]
    title_positions: list[int] = []
    for index, item in enumerate(outline, start=1):
        if not isinstance(item, dict):
            findings.append({"severity": "CRITICAL", "message": f"planned_outline 第 {index} 项不是对象"})
            continue
        title = str(item.get("title", "")).strip()
        label = str(item.get("section_id", "")).strip() or title or f"第 {index} 个标题"
        if not title:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "planned_outline 缺少 title"})
            continue
        normalized_title = normalize_label(title)
        matched_positions = [
            pos
            for pos, normalized_heading in enumerate(normalized_headings)
            if normalized_heading == normalized_title
            or (min(len(normalized_heading), len(normalized_title)) >= 6 and normalized_title in normalized_heading)
        ]
        if not matched_positions:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": f"初稿缺少规划标题：{title}"})
        else:
            title_positions.append(matched_positions[0])

    if title_positions and title_positions != sorted(title_positions):
        findings.append({"severity": "CRITICAL", "message": "初稿标题顺序与 planned_outline 不一致"})

    task_scoring_ids = collect_ids(task.get("scoring_items", []), ("scoring_item_id", "id"))
    task_scoring_ids.update(collect_ids(outline, ("scoring_item_id", "scoring_item_ids")))
    task_requirement_ids = collect_ids(task.get("atomic_requirement_ids", []), ("requirement_id", "id"))
    task_requirement_ids.update(collect_ids(task.get("mandatory_requirements", []), ("requirement_id", "id")))
    task_requirement_ids.update(collect_ids(outline, ("requirement_id", "requirement_ids")))

    evidence_text = json.dumps(evidence, ensure_ascii=False) if evidence is not None else ""
    draft_and_evidence = f"{draft}\n{evidence_text}"
    for scoring_id in sorted(task_scoring_ids):
        if scoring_id and scoring_id not in draft_and_evidence:
            findings.append({"severity": "MAJOR", "message": f"评分项 {scoring_id} 未在初稿或证据文件中定位"})
    for requirement_id in sorted(task_requirement_ids):
        if requirement_id and requirement_id not in draft_and_evidence:
            findings.append({"severity": "MAJOR", "message": f"原子要求 {requirement_id} 未在初稿或证据文件中定位"})

    if evidence is None:
        findings.append({"severity": "MAJOR", "message": "缺少 evidence 文件，无法确认初稿证据链"})
    else:
        evidence_report = validate_chapter_evidence(
            evidence,
            str(task.get("task_id", "")).strip(),
            paragraph_plan,
        )
        for item in evidence_report["findings"]:
            findings.append({"severity": item.get("severity", "MAJOR"), "message": f"evidence 问题：{item.get('message', '')}"})

    forbidden_patterns = ("第1页", "第 1 页", "模板A", "模板 A", "模板B", "模板 B")
    if any(pattern in draft for pattern in forbidden_patterns):
        findings.append({"severity": "MAJOR", "message": "初稿疑似包含页级模板轮转痕迹"})

    if task.get("grounding_pack_file") and grounding_pack is None:
        findings.append({"severity": "CRITICAL", "message": "任务书声明了 grounding_pack_file，但检查时未提供章节依据包"})
    if task.get("paragraph_plan_file") and paragraph_plan is None:
        findings.append({"severity": "CRITICAL", "message": "任务书声明了 paragraph_plan_file，但检查时未提供段落写作计划"})
    if grounding_pack is not None:
        grounding_report = validate_grounding_pack(grounding_pack)
        for item in grounding_report["findings"]:
            findings.append({"severity": item.get("severity", "MAJOR"), "message": f"章节依据包问题：{item.get('message', '')}"})
    if paragraph_plan is not None:
        paragraph_report = validate_paragraph_plan(paragraph_plan, grounding_pack)
        for item in paragraph_report["findings"]:
            findings.append({"severity": item.get("severity", "MAJOR"), "message": f"段落写作计划问题：{item.get('message', '')}"})
        paragraph_plan_ids = collect_ids(paragraph_plan, ("paragraph_plan_id",))
        if paragraph_plan_ids:
            located_ids = collect_ids(evidence or {}, ("paragraph_plan_id", "paragraph_plan_ids"))
            missing_plan_ids = paragraph_plan_ids - located_ids
            if missing_plan_ids:
                findings.append({"severity": "MAJOR", "message": f"段落计划未在 evidence 中定位：{sorted(missing_plan_ids)}"})
        for paragraph in paragraph_plan.get("paragraphs", []):
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = str(paragraph.get("paragraph_plan_id", "")).strip() or "<unknown>"
            actions = [str(item) for item in paragraph.get("required_actions", []) if str(item).strip()]
            controls_and_outputs = [
                str(item)
                for key in ("control_points", "deliverables")
                for item in paragraph.get(key, [])
                if str(item).strip()
            ]
            if actions and not any(action in draft for action in actions):
                findings.append({"severity": "MAJOR", "message": f"段落计划 {paragraph_id} 的执行动作未在初稿中落位"})
            if controls_and_outputs and not any(item in draft for item in controls_and_outputs):
                findings.append({"severity": "MAJOR", "message": f"段落计划 {paragraph_id} 的控制节点或交付成果未在初稿中落位"})
    keywords = plan_keywords(paragraph_plan, grounding_pack)
    if keywords:
        matched_keywords = [keyword for keyword in keywords if keyword in draft]
        if len(matched_keywords) < min(3, len(keywords)):
            findings.append({"severity": "MAJOR", "message": "初稿未充分体现章节依据包或段落计划中的项目关键词、动作或交付物"})

    findings.extend(forbidden_phrase_findings(draft))
    findings.extend(generic_rhetoric_findings(draft))
    findings.extend(unconfirmed_claim_findings(draft, evidence))
    findings.extend(rejection_risk_findings(draft))

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "planned_heading_count": len(outline),
        "draft_heading_count": len(headings),
        "scoring_item_count": len(task_scoring_ids),
        "atomic_requirement_count": len(task_requirement_ids),
        "findings": findings,
    }


def validate_requirement_register(data: dict) -> dict:
    findings: list[dict] = []
    records = data.get("records")
    if not isinstance(records, list) or not records:
        return {
            "status": "REJECT",
            "record_count": 0,
            "rejection_clause_count": 0,
            "marked_item_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "原子要点台账 records 为空或不存在"}],
        }

    seen_ids: set[str] = set()
    rejection_count = 0
    marked_count = 0
    for index, record in enumerate(records, start=1):
        requirement_id = str(record.get("requirement_id", "")).strip()
        label = requirement_id or f"第 {index} 条"
        if not requirement_id:
            findings.append({"severity": "CRITICAL", "requirement_id": label, "message": "缺少 requirement_id"})
        elif requirement_id in seen_ids:
            findings.append({"severity": "CRITICAL", "requirement_id": label, "message": "requirement_id 重复"})
        seen_ids.add(requirement_id)

        for field in ("original_text", "atomic_requirement", "item_type", "applicable_package"):
            if not str(record.get(field, "")).strip():
                findings.append({"severity": "CRITICAL", "requirement_id": label, "message": f"缺少 {field}"})

        source = record.get("source", {})
        if not isinstance(source, dict) or not str(source.get("file", "")).strip():
            findings.append({"severity": "CRITICAL", "requirement_id": label, "message": "缺少来源文件"})
        if not isinstance(source, dict) or not (
            str(source.get("page", "")).strip() or str(source.get("section_path", "")).strip()
        ):
            findings.append({"severity": "MAJOR", "requirement_id": label, "message": "缺少页码或章节路径"})

        raw_markers = record.get("raw_markers", [])
        flags = record.get("marker_flags", {})
        if not isinstance(flags, dict):
            flags = {}
        if not isinstance(raw_markers, list):
            findings.append({"severity": "CRITICAL", "requirement_id": label, "message": "raw_markers 必须为数组"})
            raw_markers = []
        has_asterisk = "*" in raw_markers or bool(flags.get("asterisk"))
        has_star = "⭐" in raw_markers or bool(flags.get("star"))
        has_rejection = record.get("item_type") == "rejection_clause" or bool(flags.get("rejection")) or any(
            marker in str(record.get("original_text", ""))
            for marker in ("废标", "否决", "无效投标", "投标无效", "不予受理")
        )
        if has_asterisk or has_star or has_rejection:
            marked_count += 1
        if (has_asterisk or has_star) and not record.get("marker_meaning_confirmed"):
            findings.append(
                {
                    "severity": "CRITICAL",
                    "requirement_id": label,
                    "message": "* 或 ⭐ 标记含义尚未确认",
                }
            )
        if has_rejection:
            rejection_count += 1
            consequence = record.get("rejection_consequence", {})
            if not isinstance(consequence, dict) or not str(consequence.get("consequence_text", "")).strip():
                findings.append(
                    {"severity": "BLOCKER", "requirement_id": label, "message": "废标/否决项缺少后果原文"}
                )
            if not isinstance(consequence, dict) or not str(consequence.get("trigger_condition", "")).strip():
                findings.append(
                    {"severity": "BLOCKER", "requirement_id": label, "message": "废标/否决项缺少触发条件"}
                )
            if not isinstance(consequence, dict) or not consequence.get("human_confirmed"):
                findings.append(
                    {"severity": "BLOCKER", "requirement_id": label, "message": "废标/否决项尚未人工确认"}
                )

        response = record.get("response", {})
        if not isinstance(response, dict) or not str(response.get("primary_chapter", "")).strip():
            findings.append({"severity": "CRITICAL", "requirement_id": label, "message": "缺少主响应章节"})

    severities = {item["severity"] for item in findings}
    if "BLOCKER" in severities:
        status = "REJECT"
    elif severities.intersection({"CRITICAL", "MAJOR"}):
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"
    return {
        "status": status,
        "record_count": len(records),
        "rejection_clause_count": rejection_count,
        "marked_item_count": marked_count,
        "findings": findings,
    }


def validate_marker_register(data: dict) -> dict:
    findings: list[dict] = []
    markers = data.get("markers")
    if not isinstance(markers, list) or not markers:
        return {
            "status": "REJECT",
            "marker_count": 0,
            "confirmed_marker_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "特殊标记台账 markers 为空或不存在"}],
        }

    seen: set[str] = set()
    confirmed_count = 0
    for index, marker in enumerate(markers, start=1):
        marker_id = str(marker.get("marker_id", "")).strip()
        raw_marker = str(marker.get("raw_marker", "")).strip()
        label = marker_id or raw_marker or f"第 {index} 条"
        if not marker_id:
            findings.append({"severity": "CRITICAL", "marker_id": label, "message": "缺少 marker_id"})
        elif marker_id in seen:
            findings.append({"severity": "CRITICAL", "marker_id": label, "message": "marker_id 重复"})
        seen.add(marker_id)

        if not raw_marker:
            findings.append({"severity": "CRITICAL", "marker_id": label, "message": "缺少 raw_marker"})
        if not str(marker.get("meaning", "")).strip():
            findings.append({"severity": "CRITICAL", "marker_id": label, "message": "缺少标记含义"})
        if marker.get("confirmed"):
            confirmed_count += 1
        else:
            findings.append({"severity": "CRITICAL", "marker_id": label, "message": "标记含义尚未确认"})

        source = marker.get("meaning_source", {})
        if not isinstance(source, dict) or not str(source.get("file", "")).strip():
            findings.append({"severity": "MAJOR", "marker_id": label, "message": "缺少标记含义来源文件"})
        if not isinstance(source, dict) or not str(source.get("original_text", "")).strip():
            findings.append({"severity": "MAJOR", "marker_id": label, "message": "缺少标记含义来源原文"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities else "PASS"
    return {
        "status": status,
        "marker_count": len(markers),
        "confirmed_marker_count": confirmed_count,
        "findings": findings,
    }


def validate_rejection_clauses(data: dict) -> dict:
    findings: list[dict] = []
    clauses = data.get("clauses")
    if not isinstance(clauses, list):
        return {
            "status": "REJECT",
            "clause_count": 0,
            "confirmed_clause_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "废标/否决条款 clauses 不存在或不是数组"}],
        }

    seen: set[str] = set()
    confirmed_count = 0
    for index, clause in enumerate(clauses, start=1):
        clause_id = str(clause.get("rejection_clause_id", "")).strip()
        label = clause_id or f"第 {index} 条"
        if not clause_id:
            findings.append({"severity": "CRITICAL", "rejection_clause_id": label, "message": "缺少 rejection_clause_id"})
        elif clause_id in seen:
            findings.append({"severity": "CRITICAL", "rejection_clause_id": label, "message": "rejection_clause_id 重复"})
        seen.add(clause_id)

        for field in ("requirement_id", "trigger_condition", "consequence_text", "original_text", "applicable_package"):
            if not str(clause.get(field, "")).strip():
                findings.append({"severity": "BLOCKER", "rejection_clause_id": label, "message": f"缺少 {field}"})

        source = clause.get("source", {})
        if not isinstance(source, dict) or not str(source.get("file", "")).strip():
            findings.append({"severity": "BLOCKER", "rejection_clause_id": label, "message": "缺少来源文件"})
        if not isinstance(source, dict) or not (
            str(source.get("page", "")).strip() or str(source.get("section_path", "")).strip()
        ):
            findings.append({"severity": "MAJOR", "rejection_clause_id": label, "message": "缺少页码或章节路径"})

        if clause.get("human_confirmed"):
            confirmed_count += 1
        else:
            findings.append({"severity": "BLOCKER", "rejection_clause_id": label, "message": "废标/否决条款尚未人工确认"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities else "PASS"
    return {
        "status": status,
        "clause_count": len(clauses),
        "confirmed_clause_count": confirmed_count,
        "findings": findings,
    }


def validate_requirement_cross_refs(requirements: dict, markers: dict, rejections: dict) -> dict:
    findings: list[dict] = []
    records = requirements.get("records", [])
    marker_values = {
        str(marker.get("raw_marker", "")).strip()
        for marker in markers.get("markers", [])
        if str(marker.get("raw_marker", "")).strip()
    }
    rejection_requirement_ids = {
        str(clause.get("requirement_id", "")).strip()
        for clause in rejections.get("clauses", [])
        if str(clause.get("requirement_id", "")).strip()
    }
    requirement_ids = {
        str(record.get("requirement_id", "")).strip()
        for record in records
        if str(record.get("requirement_id", "")).strip()
    }

    for record in records:
        requirement_id = str(record.get("requirement_id", "")).strip()
        raw_markers = record.get("raw_markers", [])
        flags = record.get("marker_flags", {})
        if not isinstance(raw_markers, list):
            raw_markers = []
        if not isinstance(flags, dict):
            flags = {}

        for raw_marker in raw_markers:
            if raw_marker in {"废标", "否决", "无效投标", "投标无效", "不予受理"}:
                continue
            if raw_marker not in marker_values:
                findings.append(
                    {
                        "severity": "CRITICAL",
                        "requirement_id": requirement_id,
                        "message": f"原子要点使用标记 {raw_marker}，但 marker-register 未登记",
                    }
                )

        has_rejection = record.get("item_type") == "rejection_clause" or bool(flags.get("rejection")) or any(
            marker in str(record.get("original_text", ""))
            for marker in ("废标", "否决", "无效投标", "投标无效", "不予受理")
        )
        if has_rejection and requirement_id not in rejection_requirement_ids:
            findings.append(
                {
                    "severity": "BLOCKER",
                    "requirement_id": requirement_id,
                    "message": "原子要点为废标/否决项，但 rejection-clauses 未登记",
                }
            )

    for rejection_requirement_id in rejection_requirement_ids:
        if rejection_requirement_id not in requirement_ids:
            findings.append(
                {
                    "severity": "BLOCKER",
                    "requirement_id": rejection_requirement_id,
                    "message": "rejection-clauses 引用的 requirement_id 不存在于原子要点台账",
                }
            )

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities else "PASS"
    return {"status": status, "findings": findings}


def validate_source_readiness(data: dict) -> dict:
    findings: list[dict] = []
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return {
            "status": "REJECT",
            "source_count": 0,
            "blocking_source_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "资料可读性台账 sources 为空或不存在"}],
        }

    core_types = {
        "tender",
        "technical_specification",
        "technical_scoring",
        "scoring_rules",
        "technical_bid_format",
        "format_rules",
    }
    required_core_types = {"tender", "technical_specification"}
    seen_required_core_types: set[str] = set()
    seen_ids: set[str] = set()

    def source_role(source: dict) -> str:
        role = str(source.get("source_role", "")).strip().lower()
        if role:
            return role
        if source.get("current_project_core") is True:
            return "core"
        source_type = str(source.get("source_type", "")).strip()
        if source_type in core_types:
            return "core"
        return "reference"

    def add_parse_finding(source: dict, label: str, message: str) -> None:
        role = source_role(source)
        severity = "BLOCKER" if role == "core" else "MAJOR"
        finding = {"severity": severity, "source_id": label, "message": message}
        if role != "core":
            finding["action"] = "降低引用优先级或排除出 RAG 检索范围"
        findings.append(finding)

    def parse_confidence_untrusted(source: dict) -> bool:
        value = source.get("parse_confidence")
        if value is None or value == "":
            return False
        if isinstance(value, (int, float)):
            return float(value) < 0.7
        normalized = str(value).strip().upper()
        return normalized in {"LOW", "FAILED", "UNRELIABLE", "UNTRUSTED"}

    for index, source in enumerate(sources, start=1):
        source_id = str(source.get("source_id", "")).strip()
        label = source_id or f"第 {index} 条"
        source_type = str(source.get("source_type", "")).strip()
        role = source_role(source)
        if source_id in seen_ids:
            findings.append({"severity": "CRITICAL", "source_id": label, "message": "source_id 重复"})
        seen_ids.add(source_id)
        if not source_id:
            findings.append({"severity": "CRITICAL", "source_id": label, "message": "缺少 source_id"})
        if not str(source.get("file", "")).strip():
            findings.append({"severity": "CRITICAL", "source_id": label, "message": "缺少文件路径"})
        if role == "core" and source_type in required_core_types:
            seen_required_core_types.add(source_type)
        if source.get("exists") is not True:
            add_parse_finding(source, label, "来源文件不存在或未确认存在")
            continue
        if not is_positive(source.get("text_extractable")):
            add_parse_finding(source, label, "资料文本不可稳定抽取")
        if source.get("contains_key_tables") and not (
            is_positive(source.get("table_extractable")) or is_positive(source.get("manual_table_reviewed"))
        ):
            add_parse_finding(source, label, "资料关键表格不可稳定抽取且尚未人工复核")
        if source.get("requires_conversion") and source.get("conversion_status") != "DONE":
            add_parse_finding(source, label, "资料需要解析或转换但尚未完成可信复核")
        if str(source.get("readability", "")).upper() in {"UNREADABLE", "FAILED"}:
            add_parse_finding(source, label, "资料可读性或解析结果不可信")
        if parse_confidence_untrusted(source):
            add_parse_finding(source, label, "资料解析可信度低")
        if role == "core" and source.get("structure_extractable") is False:
            add_parse_finding(source, label, "核心依据文件章节结构不可稳定解析")

    for required_type in required_core_types:
        if required_type not in seen_required_core_types:
            findings.append({"severity": "BLOCKER", "message": f"缺少核心依据资料类型：{required_type}"})

    blocking_count = sum(1 for item in findings if item["severity"] == "BLOCKER")
    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities else "PASS"
    return {
        "status": status,
        "source_count": len(sources),
        "blocking_source_count": blocking_count,
        "findings": findings,
    }


def update_section_stack(stack: list[str], text: str) -> list[str]:
    level = heading_level(text)
    if level is None:
        return stack
    next_stack = stack[: max(level - 1, 0)]
    next_stack.append(text.strip())
    return next_stack


def make_fragment(
    source_id: str,
    fragment_id: str,
    text: str,
    page: int | None = None,
    section_path: list[str] | None = None,
    paragraph_index: int | None = None,
    table: dict | None = None,
) -> dict:
    location: dict[str, object] = {}
    if page is not None:
        location["page"] = page
    if section_path:
        location["section_path"] = " > ".join(section_path)
    if paragraph_index is not None:
        location["paragraph_index"] = paragraph_index
    if table:
        location["table"] = table
    return {
        "fragment_id": fragment_id,
        "source_id": source_id,
        "kind": "table" if table else "text",
        "location": location,
        "text": text.strip(),
        "char_count": len(text.strip()),
    }


def parse_pdf(path: Path, source_id: str) -> tuple[list[dict], dict]:
    pypdf = try_import("pypdf")
    if pypdf is None:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "txt",
            "conversion_status": "PENDING",
            "notes": "缺少 pypdf，无法解析 PDF",
        }

    fragments: list[dict] = []
    section_stack: list[str] = []
    page_count = 0
    text_pages = 0
    try:
        reader = pypdf.PdfReader(str(path))
        page_count = len(reader.pages)
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                text_pages += 1
            blocks = [block.strip() for block in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if block.strip()]
            if not blocks:
                blocks = [line.strip() for line in text.splitlines() if line.strip()]
            for index, block in enumerate(blocks, start=1):
                section_stack = update_section_stack(section_stack, block)
                fragments.append(
                    make_fragment(
                        source_id,
                        f"{source_id}-P{page_number:03d}-{index:03d}",
                        block,
                        page=page_number,
                        section_path=section_stack,
                        paragraph_index=index,
                    )
                )
    except Exception as exc:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "manual-excerpt",
            "conversion_status": "PENDING",
            "notes": f"PDF 解析失败：{exc}",
        }

    text_extractable = bool(fragments)
    return fragments, {
        "readability": "READABLE" if text_extractable else "UNREADABLE",
        "text_extractable": text_extractable,
        "table_extractable": False,
        "structure_extractable": text_extractable,
        "parse_confidence": "HIGH" if page_count and text_pages / max(page_count, 1) >= 0.8 else "LOW",
        "requires_conversion": not text_extractable,
        "conversion_target": "" if text_extractable else "manual-excerpt",
        "conversion_status": "NOT_REQUIRED" if text_extractable else "PENDING",
        "page_count": page_count,
        "notes": "PDF 表格未做稳定抽取，关键表格需人工复核",
    }


def parse_docx(path: Path, source_id: str) -> tuple[list[dict], dict]:
    docx = try_import("docx")
    if docx is None:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "txt",
            "conversion_status": "PENDING",
            "notes": "缺少 python-docx，无法解析 DOCX",
        }

    fragments: list[dict] = []
    section_stack: list[str] = []
    table_count = 0
    try:
        document = docx.Document(str(path))
        for index, paragraph in enumerate(document.paragraphs, start=1):
            text = paragraph.text.strip()
            if not text:
                continue
            section_stack = update_section_stack(section_stack, text)
            fragments.append(make_fragment(source_id, f"{source_id}-PARA-{index:04d}", text, section_path=section_stack, paragraph_index=index))
        for table_index, table in enumerate(document.tables, start=1):
            rows = []
            for row in table.rows:
                values = [cell.text.strip() for cell in row.cells]
                if any(values):
                    rows.append(values)
            if not rows:
                continue
            table_count += 1
            text = "\n".join(" | ".join(row) for row in rows)
            fragments.append(
                make_fragment(
                    source_id,
                    f"{source_id}-TABLE-{table_index:03d}",
                    text,
                    section_path=section_stack,
                    table={"table_index": table_index, "row_count": len(rows), "column_count": max(len(row) for row in rows)},
                )
            )
    except Exception as exc:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "manual-excerpt",
            "conversion_status": "PENDING",
            "notes": f"DOCX 解析失败：{exc}",
        }

    text_extractable = bool(fragments)
    return fragments, {
        "readability": "READABLE" if text_extractable else "UNREADABLE",
        "text_extractable": text_extractable,
        "table_extractable": bool(table_count),
        "structure_extractable": text_extractable,
        "parse_confidence": "HIGH" if text_extractable else "LOW",
        "contains_key_tables": bool(table_count),
        "requires_conversion": False,
        "conversion_target": "",
        "conversion_status": "NOT_REQUIRED",
        "table_count": table_count,
        "notes": "",
    }


def parse_xlsx(path: Path, source_id: str) -> tuple[list[dict], dict]:
    openpyxl = try_import("openpyxl")
    if openpyxl is None:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "csv",
            "conversion_status": "PENDING",
            "notes": "缺少 openpyxl，无法解析 XLSX",
        }

    fragments: list[dict] = []
    sheet_count = 0
    try:
        workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        try:
            sheet_count = len(workbook.worksheets)
            for sheet in workbook.worksheets:
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value).strip() for value in row]
                    if any(values):
                        rows.append(values)
                if not rows:
                    continue
                text = "\n".join(" | ".join(row) for row in rows)
                fragments.append(
                    make_fragment(
                        source_id,
                        f"{source_id}-SHEET-{slugify(sheet.title)}",
                        text,
                        table={
                            "sheet": sheet.title,
                            "range": sheet.calculate_dimension(),
                            "row_count": len(rows),
                            "column_count": max(len(row) for row in rows),
                        },
                    )
                )
        finally:
            workbook.close()
    except Exception as exc:
        return [], {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "requires_conversion": True,
            "conversion_target": "manual-excerpt",
            "conversion_status": "PENDING",
            "notes": f"XLSX 解析失败：{exc}",
        }

    table_extractable = bool(fragments)
    return fragments, {
        "readability": "READABLE" if table_extractable else "UNREADABLE",
        "text_extractable": table_extractable,
        "table_extractable": table_extractable,
        "structure_extractable": table_extractable,
        "parse_confidence": "HIGH" if table_extractable else "LOW",
        "contains_key_tables": table_extractable,
        "requires_conversion": False,
        "conversion_target": "",
        "conversion_status": "NOT_REQUIRED",
        "sheet_count": sheet_count,
        "notes": "",
    }


def parse_source_file(path: Path, source_id: str) -> tuple[list[dict], dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, source_id)
    if suffix == ".docx":
        return parse_docx(path, source_id)
    if suffix in {".xlsx", ".xlsm"}:
        return parse_xlsx(path, source_id)
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        fragments = []
        section_stack: list[str] = []
        for index, block in enumerate(markdown_blocks(text), start=1):
            section_stack = update_section_stack(section_stack, block)
            fragments.append(make_fragment(source_id, f"{source_id}-TEXT-{index:04d}", block, section_path=section_stack, paragraph_index=index))
        return fragments, {
            "readability": "READABLE" if fragments else "UNREADABLE",
            "text_extractable": bool(fragments),
            "table_extractable": False,
            "structure_extractable": bool(fragments),
            "parse_confidence": "HIGH" if fragments else "LOW",
            "requires_conversion": False,
            "conversion_target": "",
            "conversion_status": "NOT_REQUIRED",
            "notes": "",
        }
    return [], {
        "readability": "UNREADABLE",
        "text_extractable": False,
        "table_extractable": False,
        "structure_extractable": False,
        "parse_confidence": "FAILED",
        "requires_conversion": True,
        "conversion_target": "pdf/docx/xlsx/txt",
        "conversion_status": "PENDING",
        "notes": f"暂不支持的文件格式：{suffix or '无扩展名'}",
    }


def iter_project_sources(project_dir: Path, project: dict) -> list[tuple[Path, str]]:
    sources_root = project_dir / "sources"
    entries: list[tuple[Path, str]] = []
    for group, files in project.get("sources", {}).items():
        source_type = normalize_source_type(group)
        if not isinstance(files, list):
            continue
        for item in files:
            if not str(item).strip():
                continue
            raw_path = Path(str(item))
            path = raw_path if raw_path.is_absolute() else project_dir / raw_path
            entries.append((path, source_type))
    if entries:
        return entries
    if not sources_root.exists():
        return []
    for path in sorted(sources_root.rglob("*")):
        if path.is_file():
            entries.append((path, infer_source_type(path, project_dir)))
    return entries


def ingest_sources(project_dir: Path) -> dict:
    project_path = project_dir / "project.json"
    project = load_json(project_path) if project_path.exists() else {"project_name": project_dir.name, "package_name": "", "sources": {}}
    entries = iter_project_sources(project_dir, project)
    sources: list[dict] = []
    fragments: list[dict] = []
    registered_sources: dict[str, list[str]] = {"tender": [], "technical_specification": [], "historical_reference": [], "supporting_material": []}

    for index, (path, source_type) in enumerate(entries, start=1):
        source_id = f"SRC-{index:03d}"
        exists = path.exists()
        file_format = path.suffix.lower().lstrip(".") or "unknown"
        source_role = source_role_for_type(source_type)
        parse_meta = {
            "readability": "UNREADABLE",
            "text_extractable": False,
            "table_extractable": False,
            "structure_extractable": False,
            "parse_confidence": "FAILED",
            "contains_key_tables": False,
            "manual_table_reviewed": False,
            "requires_conversion": True,
            "conversion_target": "manual-excerpt",
            "conversion_status": "PENDING",
            "notes": "来源文件不存在",
        }
        parsed_fragments: list[dict] = []
        if exists:
            parsed_fragments, parse_meta = parse_source_file(path, source_id)
        contains_key_tables = bool(parse_meta.get("contains_key_tables")) or file_format in {"xlsx", "xlsm"}
        if file_format == "pdf" and source_role == "core":
            contains_key_tables = True
        source_record = {
            "source_id": source_id,
            "file": str(path.relative_to(project_dir)) if path.is_absolute() and path.exists() else str(path),
            "source_type": source_type,
            "source_role": source_role,
            "format": file_format,
            "exists": exists,
            "readability": parse_meta.get("readability", "UNREADABLE"),
            "text_extractable": parse_meta.get("text_extractable", False),
            "table_extractable": parse_meta.get("table_extractable", False),
            "structure_extractable": parse_meta.get("structure_extractable", False),
            "parse_confidence": parse_meta.get("parse_confidence", "FAILED"),
            "contains_key_tables": contains_key_tables,
            "manual_table_reviewed": False,
            "requires_conversion": parse_meta.get("requires_conversion", False),
            "conversion_target": parse_meta.get("conversion_target", ""),
            "conversion_status": parse_meta.get("conversion_status", "NOT_REQUIRED"),
            "rag_eligible": source_role != "core" and parse_meta.get("text_extractable") is True,
            "degradation_action": "" if source_role == "core" else "低可信时排除出 RAG 检索范围",
            "page_or_section_scope": "",
            "risk": "LOW" if parse_meta.get("parse_confidence") == "HIGH" else "HIGH" if source_role == "core" else "MEDIUM",
            "notes": parse_meta.get("notes", ""),
        }
        if "page_count" in parse_meta:
            source_record["page_count"] = parse_meta["page_count"]
        if "table_count" in parse_meta:
            source_record["table_count"] = parse_meta["table_count"]
        if "sheet_count" in parse_meta:
            source_record["sheet_count"] = parse_meta["sheet_count"]
        sources.append(source_record)
        fragments.extend(parsed_fragments)
        group = source_group_for_type(source_type)
        registered_sources.setdefault(group, []).append(source_record["file"])

    readiness = {
        "version": 1,
        "project_name": project.get("project_name", ""),
        "package_name": project.get("package_name", ""),
        "target_package_confirmed": bool(project.get("package_confirmed")),
        "sources": sources,
        "blocking_items": [],
        "human_confirmations": [],
    }
    readiness_report = validate_source_readiness(readiness) if sources else {
        "status": "REJECT",
        "source_count": 0,
        "blocking_source_count": 0,
        "findings": [{"severity": "BLOCKER", "message": "未发现可入库来源文件"}],
    }
    readiness["blocking_items"] = [item for item in readiness_report.get("findings", []) if item.get("severity") == "BLOCKER"]

    source_index = {
        "version": 1,
        "project_name": project.get("project_name", ""),
        "package_name": project.get("package_name", ""),
        "generated_by": "ingest-sources",
        "sources": sources,
        "fragments": fragments,
        "fragment_count": len(fragments),
    }
    write_json(project_dir / "inventory" / "source-readiness.json", readiness)
    write_json(project_dir / "inventory" / "source-index.json", source_index)
    if project_path.exists():
        project_sources = project.setdefault("sources", {})
        for group, files in registered_sources.items():
            if files:
                project_sources[group] = files
        write_json(project_path, project)

    return {
        "status": readiness_report["status"],
        "source_count": len(sources),
        "fragment_count": len(fragments),
        "outputs": ["inventory/source-readiness.json", "inventory/source-index.json"],
        "findings": readiness_report.get("findings", []),
    }


def scoring_group_source_segments(group: dict) -> list[dict]:
    segments = group.get("source_segments")
    if isinstance(segments, list) and segments:
        return [segment for segment in segments if isinstance(segment, dict)]
    source = group.get("source")
    if isinstance(source, dict) and source:
        return [
            {
                "segment_id": f"LEGACY-{str(group.get('scoring_group_id', '')).strip() or 'SCG'}",
                "source_id": str(source.get("source_id", "")).strip() or str(source.get("file", "")).strip(),
                "location_type": "LEGACY_LOCATION",
                "start_locator": {
                    "page": source.get("page", ""),
                    "section_path": source.get("section_path", ""),
                    "anchor_text": source.get("anchor_text", ""),
                },
                "end_locator": {},
                "original_scope_text": source.get("original_scope_text", ""),
            }
        ]
    return []


def locator_has_value(segment: dict) -> bool:
    locator_keys = (
        "page",
        "printed_page",
        "section_path",
        "anchor_text",
        "sheet",
        "cell",
        "table_id",
        "fragment_id",
        "paragraph_id",
    )
    for key in ("start_locator", "end_locator"):
        locator = segment.get(key, {})
        if isinstance(locator, dict) and any(str(locator.get(item, "")).strip() for item in locator_keys):
            return True
    return bool(segment.get("included_fragment_ids"))


def selected_scoring_group_ids(data: dict) -> set[str]:
    explicit = collect_ids(data.get("selected_scoring_group_ids", []), ("scoring_group_id",))
    if explicit:
        return explicit
    selected: set[str] = set()
    for group in data.get("scoring_groups", []):
        if not isinstance(group, dict):
            continue
        if group.get("selected_for_current_package") or str(group.get("selection_status", "")).upper() == "SELECTED":
            group_id = str(group.get("scoring_group_id", "")).strip()
            if group_id:
                selected.add(group_id)
    return selected


def validate_scoring_applicability(data: dict, package_name: str, scoring_map: dict | None = None) -> dict:
    findings: list[dict] = []
    groups = data.get("scoring_groups")
    if not isinstance(groups, list) or not groups:
        return {
            "status": "REJECT",
            "selected_group_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "评分适用范围台账 scoring_groups 为空或不存在"}],
        }

    version = parse_int(data.get("version"), 1)
    current_package = data.get("current_package", {})
    if not isinstance(current_package, dict):
        current_package = {}
    canonical_package = str(current_package.get("canonical_name", "")).strip() or package_name
    package_id = str(current_package.get("package_id", "")).strip()
    package_aliases = [str(item).strip() for item in current_package.get("aliases", []) if str(item).strip()]
    package_candidates = [canonical_package, package_name, package_id, *package_aliases]
    if version >= 2 and not current_package.get("human_confirmed"):
        findings.append({"severity": "BLOCKER", "message": "current_package 尚未人工确认"})

    explicit_selected = collect_ids(data.get("selected_scoring_group_ids", []), ("scoring_group_id",))
    explicit_excluded = collect_ids(data.get("excluded_scoring_group_ids", []), ("scoring_group_id",))
    source_documents = data.get("source_documents", [])
    if not isinstance(source_documents, list):
        source_documents = []
    source_document_ids = collect_ids(source_documents, ("source_id",))
    if version >= 2 and not source_document_ids:
        findings.append({"severity": "CRITICAL", "message": "缺少 source_documents，无法锁定评分来源版本"})
    group_by_id: dict[str, dict] = {}
    marked_selected: set[str] = set()
    marked_excluded: set[str] = set()
    all_segment_ids: dict[str, set[str]] = {}
    global_segment_ids: set[str] = set()

    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 个评分组不是对象"})
            continue
        group_id = str(group.get("scoring_group_id", "")).strip()
        label = group_id or f"第 {index} 组"
        if not group_id:
            findings.append({"severity": "BLOCKER", "scoring_group_id": label, "message": "缺少 scoring_group_id"})
            continue
        if group_id in group_by_id:
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "scoring_group_id 重复"})
        group_by_id[group_id] = group

        group_type = str(group.get("group_type", "PACKAGE_SPECIFIC" if version >= 2 else "LEGACY")).upper()
        if version >= 2 and group_type not in SCORING_GROUP_TYPES:
            findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": f"未知 group_type：{group_type}"})
        selection_status = str(group.get("selection_status", "")).upper()
        if version >= 2 and selection_status not in SCORING_SELECTION_STATUSES:
            findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": "selection_status 必须明确为 CANDIDATE/SELECTED/EXCLUDED/CONFLICT"})
        if group.get("selected_for_current_package") or selection_status == "SELECTED":
            marked_selected.add(group_id)
        if selection_status == "EXCLUDED":
            marked_excluded.add(group_id)

        segments = scoring_group_source_segments(group)
        if not segments:
            findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": "缺少评分组来源片段 source_segments"})
        segment_ids: set[str] = set()
        for segment_index, segment in enumerate(segments, start=1):
            segment_id = str(segment.get("segment_id", "")).strip()
            if not segment_id:
                findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": f"第 {segment_index} 个来源片段缺少 segment_id"})
            elif segment_id in segment_ids:
                findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": f"segment_id 重复：{segment_id}"})
            elif segment_id in global_segment_ids:
                findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": f"segment_id 跨评分组重复：{segment_id}"})
            segment_ids.add(segment_id)
            global_segment_ids.add(segment_id)
            segment_source_id = str(segment.get("source_id", "")).strip()
            if not segment_source_id:
                findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": f"来源片段 {segment_id or segment_index} 缺少 source_id/file"})
            elif version >= 2 and source_document_ids and segment_source_id not in source_document_ids:
                findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": f"来源片段引用未登记 source_id：{segment_source_id}"})
            if not str(segment.get("original_scope_text", "")).strip():
                findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": f"来源片段 {segment_id or segment_index} 缺少适用范围原文"})
            if not locator_has_value(segment):
                findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": f"来源片段 {segment_id or segment_index} 缺少可复核的逻辑定位"})
        all_segment_ids[group_id] = segment_ids

    selected_ids = explicit_selected or marked_selected
    excluded_ids = explicit_excluded | marked_excluded
    if version >= 2 and explicit_selected != marked_selected:
        findings.append({"severity": "BLOCKER", "message": "selected_scoring_group_ids 与组内 selection_status/selected_for_current_package 不一致"})
    if version < 2 and len(selected_ids) != 1:
        findings.append({"severity": "BLOCKER", "message": f"旧版台账必须且只能选中 1 组评分标准，实际 {len(selected_ids)} 组；多组组合请升级到 version=2"})
    elif not selected_ids:
        findings.append({"severity": "BLOCKER", "message": "当前标包未选中任何评分组"})
    if selected_ids & excluded_ids:
        findings.append({"severity": "BLOCKER", "message": f"评分组同时被选中和排除：{sorted(selected_ids & excluded_ids)}"})
    unknown_selected = selected_ids - set(group_by_id)
    if unknown_selected:
        findings.append({"severity": "BLOCKER", "message": f"选中了未登记评分组：{sorted(unknown_selected)}"})

    for group_id in sorted(selected_ids & set(group_by_id)):
        group = group_by_id[group_id]
        group_type = str(group.get("group_type", "LEGACY")).upper()
        if not group.get("human_confirmed"):
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "选中评分组尚未人工确认"})
        if str(group.get("selection_status", "")).upper() == "CONFLICT":
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "冲突状态评分组不得进入编写"})

        applies_to: list[object] = list(group.get("applies_to_packages", [])) if isinstance(group.get("applies_to_packages", []), list) else []
        exclusions: list[object] = list(group.get("excluded_packages", [])) if isinstance(group.get("excluded_packages", []), list) else []
        for rule in group.get("applicability_rules", []):
            if isinstance(rule, dict):
                applies_to.extend(rule.get("package_ids", []) if isinstance(rule.get("package_ids"), list) else [])
                applies_to.extend(rule.get("package_names", []) if isinstance(rule.get("package_names"), list) else [])
                if version >= 2 and not str(rule.get("original_text", "")).strip():
                    findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": "适用规则缺少 original_text"})
        for rule in group.get("exclusion_rules", []):
            if isinstance(rule, dict):
                exclusions.extend(rule.get("package_ids", []) if isinstance(rule.get("package_ids"), list) else [])
                exclusions.extend(rule.get("package_names", []) if isinstance(rule.get("package_names"), list) else [])
        if any(label_matches(candidate, exclusions) for candidate in package_candidates if candidate):
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "选中的评分组明确排除当前标包"})
        if group_type != "GLOBAL_COMMON" and not any(label_matches(candidate, applies_to) for candidate in package_candidates if candidate):
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "选中的评分组未声明适用于当前标包"})

        superseded_by = collect_ids(group.get("superseded_by_group_ids", []), ("scoring_group_id",))
        if superseded_by & selected_ids:
            findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": f"已被选中评分组覆盖，不得继续并用：{sorted(superseded_by & selected_ids)}"})

    if data.get("unresolved_conflicts"):
        findings.append({"severity": "BLOCKER", "message": "评分组仍存在 unresolved_conflicts"})

    if scoring_map is not None:
        actual_item_ids_by_group: dict[str, set[str]] = {}
        for item in scoring_map_items(scoring_map):
            item_id = str(item.get("scoring_item_id", "")).strip()
            group_id = str(item.get("scoring_group_id", "")).strip()
            segment_id = str(item.get("source_segment_id", "")).strip()
            if not group_id:
                findings.append({"severity": "BLOCKER", "scoring_item_id": item_id, "message": "评分项缺少 scoring_group_id，无法验证标包边界"})
                continue
            actual_item_ids_by_group.setdefault(group_id, set()).add(item_id)
            if group_id not in selected_ids:
                findings.append({"severity": "BLOCKER", "scoring_item_id": item_id, "message": f"评分项来自未选中或已排除评分组：{group_id}"})
            if segment_id and segment_id not in all_segment_ids.get(group_id, set()):
                findings.append({"severity": "BLOCKER", "scoring_item_id": item_id, "message": f"评分项引用不属于评分组的来源片段：{segment_id}"})
            if version >= 2 and not segment_id:
                findings.append({"severity": "CRITICAL", "scoring_item_id": item_id, "message": "评分项缺少 source_segment_id"})
        for group_id in sorted(selected_ids & set(group_by_id)):
            declared_item_ids = collect_ids(group_by_id[group_id].get("scoring_item_ids", []), ("scoring_item_id",))
            if not declared_item_ids:
                continue
            missing_item_ids = declared_item_ids - actual_item_ids_by_group.get(group_id, set())
            if missing_item_ids:
                findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": f"评分组声明的评分项未进入 scoring-map：{sorted(missing_item_ids)}"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "selected_group_count": len(selected_ids),
        "selected_scoring_group_ids": sorted(selected_ids),
        "excluded_scoring_group_ids": sorted(excluded_ids),
        "findings": findings,
    }


def scoring_map_items(data: dict) -> list[dict]:
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def validate_scoring_map(data: dict, scoring_applicability: dict | None = None) -> dict:
    findings: list[dict] = []
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return {
            "status": "REJECT",
            "scoring_item_count": 0,
            "score_atom_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "评分映射 scoring-map.json 缺少 items"}],
        }

    scoring_item_ids: set[str] = set()
    score_atom_ids: set[str] = set()
    constraint_ids: set[str] = set()
    score_atom_count = 0
    map_selected_ids = collect_ids(data.get("selected_scoring_group_ids", []), ("scoring_group_id",))
    applicability_selected_ids = selected_scoring_group_ids(scoring_applicability or {})
    allowed_group_ids = applicability_selected_ids or map_selected_ids
    if map_selected_ids and applicability_selected_ids and map_selected_ids != applicability_selected_ids:
        findings.append({"severity": "BLOCKER", "message": "scoring-map 的 selected_scoring_group_ids 与评分适用范围台账不一致"})

    for item_index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {item_index} 个评分项不是对象"})
            continue
        scoring_item_id = str(item.get("scoring_item_id", "")).strip()
        label = scoring_item_id or f"第 {item_index} 个评分项"
        if not scoring_item_id:
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": "缺少 scoring_item_id"})
        elif scoring_item_id in scoring_item_ids:
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": "scoring_item_id 重复"})
        scoring_item_ids.add(scoring_item_id)

        scoring_group_id = str(item.get("scoring_group_id", "")).strip()
        if allowed_group_ids and not scoring_group_id:
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": "缺少 scoring_group_id，无法核验评分组边界"})
        elif scoring_group_id and allowed_group_ids and scoring_group_id not in allowed_group_ids:
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": f"评分项来自未选中评分组：{scoring_group_id}"})
        if applicability_selected_ids and not str(item.get("source_segment_id", "")).strip():
            findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": "缺少 source_segment_id，无法核验评分来源片段"})

        if not str(item.get("detailed_review_element", "")).strip():
            findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": "缺少详细评审分项要素"})
        source = item.get("source", {})
        if not isinstance(source, dict) or not str(source.get("original_text", "")).strip():
            findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": "缺少评分项来源原文"})

        highest_band = item.get("highest_score_band", {})
        if not isinstance(highest_band, dict) or not str(highest_band.get("original_text", "")).strip():
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": "缺少最高得分档原文"})

        evaluation_method = item.get("evaluation_method", {})
        if isinstance(evaluation_method, dict) and str(evaluation_method.get("original_text", "")).strip():
            if evaluation_method.get("not_a_heading") is not True:
                findings.append({"severity": "MAJOR", "scoring_item_id": label, "message": "评审方式必须标记为 not_a_heading=true"})

        global_constraints = item.get("global_constraints", [])
        if not isinstance(global_constraints, list):
            findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": "global_constraints 必须为数组"})
            global_constraints = []
        for constraint_index, constraint in enumerate(global_constraints, start=1):
            if not isinstance(constraint, dict):
                findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": f"第 {constraint_index} 个全局约束不是对象"})
                continue
            constraint_id = str(constraint.get("constraint_id", "")).strip()
            if not constraint_id:
                findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": "全局约束缺少 constraint_id"})
            elif constraint_id in constraint_ids:
                findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": f"constraint_id 重复：{constraint_id}"})
            constraint_ids.add(constraint_id)
            if not str(constraint.get("original_phrase", "")).strip():
                findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": f"全局约束 {constraint_id or constraint_index} 缺少原文短语"})

        atoms = item.get("score_atoms")
        if not isinstance(atoms, list) or not atoms:
            findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": "最高得分档尚未拆成 score_atoms"})
            continue
        atom_orders: list[int] = []
        for atom_index, atom in enumerate(atoms, start=1):
            if not isinstance(atom, dict):
                findings.append({"severity": "CRITICAL", "scoring_item_id": label, "message": f"第 {atom_index} 个评分原子不是对象"})
                continue
            score_atom_count += 1
            atom_id = str(atom.get("score_atom_id", "")).strip()
            atom_label = atom_id or f"{label} 的第 {atom_index} 个评分原子"
            if not atom_id:
                findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": f"{atom_label} 缺少 score_atom_id"})
            elif atom_id in score_atom_ids:
                findings.append({"severity": "BLOCKER", "scoring_item_id": label, "message": f"score_atom_id 重复：{atom_id}"})
            score_atom_ids.add(atom_id)
            if not str(atom.get("original_phrase", "")).strip():
                findings.append({"severity": "CRITICAL", "score_atom_id": atom_label, "message": "缺少评分原文短语 original_phrase"})
            if not str(atom.get("response_object", "")).strip():
                findings.append({"severity": "BLOCKER", "score_atom_id": atom_label, "message": "缺少可用于三级标题的 response_object"})
            if atom.get("atom_type", "content_object") != "content_object":
                findings.append({"severity": "MAJOR", "score_atom_id": atom_label, "message": "score_atoms 只应登记 content_object，质量标准和全局约束应使用独立字段"})
            if not isinstance(atom.get("quality_criteria", []), list):
                findings.append({"severity": "CRITICAL", "score_atom_id": atom_label, "message": "quality_criteria 必须为数组"})
            order = atom.get("order")
            if isinstance(order, int):
                atom_orders.append(order)
            else:
                findings.append({"severity": "MAJOR", "score_atom_id": atom_label, "message": "缺少数字型 order"})
        if atom_orders and atom_orders != sorted(atom_orders):
            findings.append({"severity": "MAJOR", "scoring_item_id": label, "message": "score_atoms 未按最高得分档原文顺序排列"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if severities.intersection({"BLOCKER", "CRITICAL"}) else "REVIEW_REQUIRED" if "MAJOR" in severities else "PASS"
    return {
        "status": status,
        "scoring_item_count": len(scoring_item_ids),
        "score_atom_count": score_atom_count,
        "findings": findings,
    }


def response_register_records(data: dict) -> list[dict]:
    records = data.get("records", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def response_fixed_texts(values: object) -> list[str]:
    texts: list[str] = []
    if isinstance(values, str) and values.strip():
        return [values.strip()]
    if not isinstance(values, list):
        return texts
    for value in values:
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
        elif isinstance(value, dict):
            for key in ("text", "phrase", "value", "fixed_text", "forbidden_text"):
                text = str(value.get(key, "")).strip()
                if text:
                    texts.append(text)
                    break
    return texts


def normalize_response_text(value: object) -> str:
    return re.sub(r"[\s:：_\-—–（）()【】\[\]、，,。.!！?？;；*`#>]+", "", str(value or "")).lower()


def response_text_contains(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_response_text(phrase)
    return bool(normalized_phrase) and normalized_phrase in normalize_response_text(text)


def validate_response_register(data: dict, requirements: dict | None = None) -> dict:
    findings: list[dict] = []
    records = data.get("records")
    if not isinstance(records, list) or not records:
        return {
            "status": "REJECT",
            "record_count": 0,
            "confirmed_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "要求—响应口径台账 records 为空或不存在"}],
        }

    seen_ids: set[str] = set()
    requirement_ids: set[str] = set()
    confirmed_count = 0
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            findings.append({"severity": "CRITICAL", "message": f"第 {index} 条响应口径不是对象"})
            continue
        response_item_id = str(record.get("response_item_id", "")).strip()
        label = response_item_id or f"第 {index} 条响应口径"
        if not response_item_id:
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "缺少 response_item_id"})
        elif response_item_id in seen_ids:
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "response_item_id 重复"})
        seen_ids.add(response_item_id)

        requirement_id = str(record.get("requirement_id", "")).strip()
        if not requirement_id:
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "缺少 requirement_id"})
        requirement_ids.add(requirement_id)

        record_type = str(record.get("record_type", "")).upper()
        response_mode = str(record.get("response_mode", "")).upper()
        status = str(record.get("status", "PENDING")).upper()
        if record_type not in RESPONSE_RECORD_TYPES:
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": f"未知 record_type：{record_type or '<empty>'}"})
        if response_mode not in RESPONSE_MODES:
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": f"未知 response_mode：{response_mode or '<empty>'}"})
        if status not in RESPONSE_STATUSES:
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": f"未知 status：{status or '<empty>'}"})

        source_requirement = record.get("source_requirement", {})
        if not isinstance(source_requirement, dict):
            source_requirement = {}
        original_text = str(source_requirement.get("original_text", "")).strip()
        if not original_text:
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "缺少招标要求原文 source_requirement.original_text"})
        if not str(source_requirement.get("source_actor", "")).strip():
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "缺少要求责任主体 source_actor"})
        if not str(source_requirement.get("action", "")).strip():
            findings.append({"severity": "MAJOR", "response_item_id": label, "message": "缺少要求动作 action"})
        if not record.get("source_refs"):
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "缺少来源引用 source_refs"})

        canonical = str(record.get("canonical_response", "")).strip()
        if status == "CONFIRMED":
            confirmed_count += 1
            if not record.get("human_confirmed"):
                findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "CONFIRMED 响应口径尚未人工确认"})
            if response_mode != "NO_DRAFT" and not canonical:
                findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "已确认响应口径缺少 canonical_response"})
        elif status in {"PENDING", "NEEDS_CONFIRMATION", "CONFLICT"} and record.get("required_in_document", True):
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": f"必答要求的响应口径仍为 {status}"})
        if record.get("required_in_document", True) and (status == "PROHIBITED" or response_mode == "NO_DRAFT"):
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "必答要求被标记为禁止写入正文，必须先完成人工裁决"})

        if response_mode == "DIRECT_COMMITMENT" and canonical:
            if "我司" not in canonical:
                findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "供应商义务必须转写为我司直接响应口径"})
            if any(phrase in canonical for phrase in ("投标人应", "供应商应", "中标人应")):
                findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "canonical_response 仍停留在招标要求视角，未转为我司响应"})
        if record_type == "PURCHASER_OBLIGATION" and response_mode != "COOPERATIVE_ACKNOWLEDGEMENT":
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "采购方义务只能采用配合理解口径，不得转写为我司直接承诺"})
        if response_mode == "COOPERATIVE_ACKNOWLEDGEMENT" and canonical and "我司" not in canonical:
            findings.append({"severity": "MAJOR", "response_item_id": label, "message": "配合理解口径应明确我司的理解或配合动作"})
        if record_type == "PROHIBITION" and response_mode != "PROHIBITION_ACKNOWLEDGEMENT":
            findings.append({"severity": "BLOCKER", "response_item_id": label, "message": "禁止性要求必须采用禁止性响应口径"})
        if response_mode == "PROHIBITION_ACKNOWLEDGEMENT" and canonical and not any(phrase in canonical for phrase in ("我司承诺不", "我司不", "我司严格禁止", "我司杜绝")):
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "禁止性响应未明确我司不实施该行为"})
        if record_type == "SCORING_EXPECTATION" and response_mode not in {"PLAN_RESPONSE", "NO_DRAFT"}:
            findings.append({"severity": "CRITICAL", "response_item_id": label, "message": "评分期待应形成方案响应，不得擅自转为额外履约承诺"})

        fixed_elements = response_fixed_texts(record.get("fixed_elements", []))
        if status == "CONFIRMED" and response_mode != "NO_DRAFT" and not fixed_elements:
            findings.append({"severity": "MAJOR", "response_item_id": label, "message": "已确认响应口径缺少 fixed_elements，无法防止扩写改变条件或范围"})
        for element in fixed_elements:
            if canonical and not response_text_contains(canonical, element):
                findings.append({"severity": "CRITICAL", "response_item_id": label, "message": f"固定要素未进入 canonical_response：{element}"})

        parameters = source_requirement.get("parameters", [])
        if isinstance(parameters, list):
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                value = str(parameter.get("value", "")).strip()
                unit = str(parameter.get("unit", "")).strip()
                if canonical and value and not response_text_contains(canonical, value):
                    findings.append({"severity": "BLOCKER", "response_item_id": label, "message": f"canonical_response 丢失要求数值：{value}"})
                if canonical and unit and not response_text_contains(canonical, unit):
                    findings.append({"severity": "BLOCKER", "response_item_id": label, "message": f"canonical_response 丢失要求单位：{unit}"})

    if data.get("conflicts"):
        findings.append({"severity": "BLOCKER", "message": "要求—响应口径台账仍存在未裁决 conflicts"})

    if requirements is not None:
        requirement_records = requirements.get("records", [])
        if not isinstance(requirement_records, list):
            requirement_records = []
        known_requirement_ids = {
            str(record.get("requirement_id", "")).strip()
            for record in requirement_records
            if isinstance(record, dict) and str(record.get("requirement_id", "")).strip()
        }
        required_requirement_ids = {
            str(record.get("requirement_id", "")).strip()
            for record in requirement_records
            if isinstance(record, dict)
            and str(record.get("requirement_id", "")).strip()
            and isinstance(record.get("response", {}), dict)
            and record.get("response", {}).get("required", True)
        }
        unknown_requirement_ids = requirement_ids - known_requirement_ids
        if unknown_requirement_ids:
            findings.append({"severity": "BLOCKER", "message": f"响应口径引用不存在的 requirement_id：{sorted(unknown_requirement_ids)}"})
        missing_requirement_ids = required_requirement_ids - requirement_ids
        if missing_requirement_ids:
            findings.append({"severity": "BLOCKER", "message": f"必答要求尚未形成我司响应口径：{sorted(missing_requirement_ids)}"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "record_count": len(records),
        "confirmed_count": confirmed_count,
        "requirement_count": len(requirement_ids),
        "findings": findings,
    }


def validate_response_content(
    response_register: dict,
    content: str,
    task: dict | None = None,
    evidence: object | None = None,
) -> dict:
    findings: list[dict] = []
    records = response_register_records(response_register)
    record_by_id = {
        str(record.get("response_item_id", "")).strip(): record
        for record in records
        if str(record.get("response_item_id", "")).strip()
    }
    requested_ids = collect_ids(task or {}, ("response_item_id", "response_item_ids"))
    if task is None:
        requested_ids = {
            response_item_id
            for response_item_id, record in record_by_id.items()
            if record.get("required_in_document", True)
            and str(record.get("status", "")).upper() == "CONFIRMED"
            and str(record.get("response_mode", "")).upper() != "NO_DRAFT"
        }
    unknown_ids = requested_ids - set(record_by_id)
    if unknown_ids:
        findings.append({"severity": "BLOCKER", "message": f"正文任务引用未登记 response_item_id：{sorted(unknown_ids)}"})

    evidence_response_ids = collect_ids(evidence or {}, ("response_item_id", "response_item_ids"))
    for response_item_id in sorted(requested_ids & set(record_by_id)):
        record = record_by_id[response_item_id]
        status = str(record.get("status", "")).upper()
        mode = str(record.get("response_mode", "")).upper()
        if status != "CONFIRMED" or not record.get("human_confirmed"):
            findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "未确认响应口径不得进入正文"})
            continue
        if mode == "NO_DRAFT" or status == "PROHIBITED":
            findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "禁止写入正文的响应口径被任务引用"})
            continue
        canonical = str(record.get("canonical_response", "")).strip()
        if canonical and not response_text_contains(content, canonical):
            findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "正文未保留已确认 canonical_response；evidence 不能替代正文响应"})
        if evidence is not None and response_item_id not in evidence_response_ids:
            findings.append({"severity": "CRITICAL", "response_item_id": response_item_id, "message": "evidence 未登记 response_item_id"})
        for element in response_fixed_texts(record.get("fixed_elements", [])):
            if not response_text_contains(content, element):
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"正文丢失响应固定要素：{element}"})
        source_requirement = record.get("source_requirement", {})
        if isinstance(source_requirement, dict):
            for parameter in source_requirement.get("parameters", []):
                if not isinstance(parameter, dict):
                    continue
                value = str(parameter.get("value", "")).strip()
                unit = str(parameter.get("unit", "")).strip()
                if value and not response_text_contains(content, value):
                    findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"正文丢失要求数值：{value}"})
                if unit and not response_text_contains(content, unit):
                    findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"正文丢失要求单位：{unit}"})
        for forbidden in response_fixed_texts(record.get("forbidden_changes", [])):
            if response_text_contains(content, forbidden):
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"正文出现禁止扩展或改变的口径：{forbidden}"})

    unexpected_evidence_ids = evidence_response_ids - requested_ids if task is not None else set()
    if unexpected_evidence_ids:
        findings.append({"severity": "CRITICAL", "message": f"evidence 出现任务未授权 response_item_id：{sorted(unexpected_evidence_ids)}"})
    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "checked_response_item_count": len(requested_ids),
        "findings": findings,
    }


def extract_scoring_item_ids(scoring_map: dict) -> set[str]:
    item_ids: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"scoring_item_id", "score_item_id"} and str(child).strip():
                    item_ids.add(str(child).strip())
                elif key in {"scoring_item_ids", "score_item_ids", "related_score_item_ids"} and isinstance(child, list):
                    item_ids.update(str(item).strip() for item in child if str(item).strip())
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(scoring_map)
    return item_ids


def validate_chapter_plan(
    plan: dict,
    requirements: dict,
    scoring_map: dict | None = None,
    response_register: dict | None = None,
) -> dict:
    findings: list[dict] = []
    sections = plan.get("sections")
    writing_tasks = plan.get("writing_tasks")
    scoring_item_mappings = plan.get("scoring_item_mappings", [])
    technical_requirement_mappings = plan.get("technical_requirement_mappings", [])
    response_item_mappings = plan.get("response_item_mappings", [])

    if not isinstance(sections, list) or not sections:
        findings.append({"severity": "BLOCKER", "message": "章节规划 sections 为空或不存在"})
        sections = []
    if not isinstance(writing_tasks, list) or not writing_tasks:
        findings.append({"severity": "BLOCKER", "message": "章节规划 writing_tasks 为空或不存在"})
        writing_tasks = []

    section_ids: set[str] = set()
    section_levels: dict[str, int] = {}
    child_counts: dict[str, int] = {}
    task_ids: set[str] = set()
    task_outputs: set[str] = set()
    section_orders: list[int] = []

    for index, section in enumerate(sections, start=1):
        section_id = str(section.get("section_id", "")).strip()
        label = section_id or f"第 {index} 节"
        level = section.get("level")
        if not section_id:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少 section_id"})
        elif section_id in section_ids:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "section_id 重复"})
        section_ids.add(section_id)
        if isinstance(level, int):
            section_levels[section_id] = level
        else:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少数字型 level"})

        if not str(section.get("title", "")).strip():
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少章节标题"})
        if level == 1 and not section.get("locked_by_tender_format"):
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "章节未声明由招标格式锁定"})
        source = section.get("source", {})
        if level == 1 and (not isinstance(source, dict) or not str(source.get("file", "")).strip()):
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少格式来源文件"})
        if level == 1 and (not isinstance(source, dict) or not str(source.get("original_text", "")).strip()):
            findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少格式来源原文"})
        order = section.get("order")
        if isinstance(order, int):
            section_orders.append(order)
        else:
            findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少数字型 order"})

        parent_section_id = str(section.get("parent_section_id", "")).strip()
        if isinstance(level, int) and level > 1:
            if not parent_section_id:
                findings.append({"severity": "CRITICAL", "section_id": label, "message": "二级及以下标题缺少 parent_section_id"})
            else:
                child_counts[parent_section_id] = child_counts.get(parent_section_id, 0) + 1
            if not str(section.get("hierarchy_role", "")).strip():
                findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少标题层级角色 hierarchy_role"})
            derived_from = str(section.get("derived_from", "")).strip()
            if not derived_from:
                findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少标题来源 derived_from"})
            mapped_scoring = [str(item).strip() for item in section.get("mapped_scoring_item_ids", []) if str(item).strip()]
            if level == 2 and not mapped_scoring and derived_from not in {"scoring_item", "detailed_review_element"}:
                findings.append({"severity": "MAJOR", "section_id": label, "message": "二级标题未记录详细评审分项要素或评分项映射"})
            if level == 3:
                scoring_derivation = section.get("scoring_derivation", {})
                if not isinstance(scoring_derivation, dict):
                    scoring_derivation = {}
                has_score_excerpt = bool(str(scoring_derivation.get("score_description_excerpt", "")).strip())
                has_keywords = bool(scoring_derivation.get("decomposition_keywords"))
                if derived_from not in {"score_description", "scoring_subpoint", "technical_requirement"} and not (
                    has_score_excerpt or has_keywords
                ):
                    findings.append({"severity": "MAJOR", "section_id": label, "message": "三级标题未记录评分描述、得分条件或技术要求拆解依据"})
            if level > 3:
                project_basis = section.get("project_specific_basis", {})
                if not isinstance(project_basis, dict):
                    project_basis = {}
                has_basis = bool(project_basis.get("technical_spec_ids")) or bool(project_basis.get("service_scope_refs")) or bool(
                    str(project_basis.get("project_context_notes", "")).strip()
                )
                if not has_basis:
                    findings.append({"severity": "MAJOR", "section_id": label, "message": "四级及以下标题缺少项目实际、技术规范书或服务范围依据"})
            if level > 4 and not section.get("manual_confirmation_required"):
                findings.append({"severity": "MAJOR", "section_id": label, "message": "标题层级超过四级时需要人工确认"})

        for task_id in section.get("writing_task_ids", []):
            if str(task_id).strip():
                task_ids.add(str(task_id).strip())

    for section in sections:
        section_id = str(section.get("section_id", "")).strip()
        parent_section_id = str(section.get("parent_section_id", "")).strip()
        level = section_levels.get(section_id)
        if level and level > 1 and parent_section_id:
            parent_level = section_levels.get(parent_section_id)
            if parent_section_id not in section_ids:
                findings.append({"severity": "BLOCKER", "section_id": section_id, "message": f"父章节不存在：{parent_section_id}"})
            elif parent_level is not None and parent_level != level - 1:
                findings.append(
                    {
                        "severity": "CRITICAL",
                        "section_id": section_id,
                        "message": f"父子层级不连续：父章节 {parent_section_id} 为 {parent_level} 级，当前为 {level} 级",
                    }
                )
    for parent_section_id, child_count in child_counts.items():
        if child_count > 5:
            findings.append({"severity": "CRITICAL", "section_id": parent_section_id, "message": f"同级子标题数量为 {child_count}，超过最多 5 个的限制"})

    if section_orders and section_orders != sorted(section_orders):
        findings.append({"severity": "MAJOR", "message": "章节 order 不是递增顺序"})

    section_by_id = {
        str(section.get("section_id", "")).strip(): section
        for section in sections
        if isinstance(section, dict) and str(section.get("section_id", "")).strip()
    }

    writing_task_ids: set[str] = set()
    task_requirement_ids: set[str] = set()
    task_scoring_item_ids: set[str] = set()
    task_response_item_ids: set[str] = set()
    for index, task in enumerate(writing_tasks, start=1):
        task_id = str(task.get("task_id", "")).strip()
        label = task_id or f"第 {index} 个任务"
        if not task_id:
            findings.append({"severity": "CRITICAL", "task_id": label, "message": "缺少 task_id"})
        elif task_id in writing_task_ids:
            findings.append({"severity": "CRITICAL", "task_id": label, "message": "task_id 重复"})
        writing_task_ids.add(task_id)

        target_section_ids = [str(item).strip() for item in task.get("target_section_ids", []) if str(item).strip()]
        if not target_section_ids:
            findings.append({"severity": "CRITICAL", "task_id": label, "message": "缺少 target_section_ids"})
        for section_id in target_section_ids:
            if section_id not in section_ids:
                findings.append({"severity": "BLOCKER", "task_id": label, "message": f"任务引用不存在的章节 {section_id}"})

        output_file = str(task.get("output_file", "")).strip()
        if not output_file:
            findings.append({"severity": "CRITICAL", "task_id": label, "message": "缺少 output_file"})
        elif output_file in task_outputs:
            findings.append({"severity": "BLOCKER", "task_id": label, "message": f"output_file 重复：{output_file}"})
        task_outputs.add(output_file)

        if not str(task.get("reason_for_split", "")).strip():
            findings.append({"severity": "MAJOR", "task_id": label, "message": "缺少拆分依据 reason_for_split"})
        task_requirement_ids.update(str(item).strip() for item in task.get("requirement_ids", []) if str(item).strip())
        task_scoring_item_ids.update(str(item).strip() for item in task.get("scoring_item_ids", []) if str(item).strip())
        task_response_item_ids.update(str(item).strip() for item in task.get("response_item_ids", []) if str(item).strip())

    unlinked_section_tasks = task_ids - writing_task_ids
    if unlinked_section_tasks:
        findings.append({"severity": "BLOCKER", "message": f"章节引用了不存在的写作任务：{sorted(unlinked_section_tasks)}"})

    records = requirements.get("records", [])
    requirement_ids = {str(record.get("requirement_id", "")).strip() for record in records if str(record.get("requirement_id", "")).strip()}
    mandatory_ids = {
        str(record.get("requirement_id", "")).strip()
        for record in records
        if str(record.get("requirement_id", "")).strip()
        and (
            record.get("item_type") in {"technical_requirement", "mandatory_requirement", "rejection_clause"}
            or bool(record.get("response", {}).get("required", True))
        )
    }
    mapped_requirement_ids = {
        str(item.get("requirement_id", "")).strip()
        for item in technical_requirement_mappings
        if isinstance(item, dict) and str(item.get("requirement_id", "")).strip()
    }
    for section in sections:
        mapped_requirement_ids.update(str(item).strip() for item in section.get("mapped_requirement_ids", []) if str(item).strip())
    mapped_requirement_ids.update(task_requirement_ids)

    missing_mandatory = mandatory_ids - mapped_requirement_ids
    if missing_mandatory:
        findings.append({"severity": "BLOCKER", "message": f"强制/必答原子要点未映射到章节或任务：{sorted(missing_mandatory)}"})
    unknown_requirements = mapped_requirement_ids - requirement_ids
    if unknown_requirements:
        findings.append({"severity": "BLOCKER", "message": f"规划引用不存在的 requirement_id：{sorted(unknown_requirements)}"})

    mapped_response_ids: set[str] = set()
    required_response_ids: set[str] = set()
    if response_register is not None:
        response_records = response_register_records(response_register)
        response_by_id = {
            str(record.get("response_item_id", "")).strip(): record
            for record in response_records
            if str(record.get("response_item_id", "")).strip()
        }
        known_response_ids = {
            str(record.get("response_item_id", "")).strip()
            for record in response_records
            if str(record.get("response_item_id", "")).strip()
        }
        required_response_ids = {
            str(record.get("response_item_id", "")).strip()
            for record in response_records
            if str(record.get("response_item_id", "")).strip()
            and record.get("required_in_document", True)
            and str(record.get("status", "")).upper() == "CONFIRMED"
            and str(record.get("response_mode", "")).upper() != "NO_DRAFT"
        }
        mapped_response_ids = {
            str(item.get("response_item_id", "")).strip()
            for item in response_item_mappings
            if isinstance(item, dict) and str(item.get("response_item_id", "")).strip()
        }
        for section in sections:
            mapped_response_ids.update(str(item).strip() for item in section.get("mapped_response_item_ids", []) if str(item).strip())
        mapped_response_ids.update(task_response_item_ids)
        missing_response_ids = required_response_ids - mapped_response_ids
        if missing_response_ids:
            findings.append({"severity": "BLOCKER", "message": f"已确认响应口径未映射到章节或任务：{sorted(missing_response_ids)}"})
        unknown_response_ids = mapped_response_ids - known_response_ids
        if unknown_response_ids:
            findings.append({"severity": "BLOCKER", "message": f"规划引用不存在的 response_item_id：{sorted(unknown_response_ids)}"})
        for mapping in response_item_mappings:
            if not isinstance(mapping, dict):
                continue
            response_item_id = str(mapping.get("response_item_id", "")).strip()
            mapping_requirement_id = str(mapping.get("requirement_id", "")).strip()
            central_requirement_id = str(response_by_id.get(response_item_id, {}).get("requirement_id", "")).strip()
            if response_item_id and central_requirement_id and mapping_requirement_id != central_requirement_id:
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": "response_item_mappings 中的 requirement_id 与中央响应台账不一致"})
            primary_section_id = str(mapping.get("primary_section_id", "")).strip()
            if response_item_id and primary_section_id not in section_ids:
                findings.append({"severity": "BLOCKER", "response_item_id": response_item_id, "message": f"响应口径主响应章节不存在：{primary_section_id or '<empty>'}"})
            for supporting_section_id in mapping.get("supporting_section_ids", []):
                if str(supporting_section_id).strip() not in section_ids:
                    findings.append({"severity": "CRITICAL", "response_item_id": response_item_id, "message": f"响应口径关联章节不存在：{supporting_section_id}"})
        for task in writing_tasks:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id", "")).strip()
            task_requirement_ids_local = collect_ids(task.get("requirement_ids", []), ("requirement_id",))
            task_response_ids_local = collect_ids(task.get("response_item_ids", []), ("response_item_id",))
            if parse_int(plan.get("version"), 1) >= 2 and task_requirement_ids_local and not task_response_ids_local:
                findings.append({"severity": "BLOCKER", "task_id": task_id, "message": "任务包含 requirement_ids 但缺少 response_item_ids"})
            for response_item_id in sorted(task_response_ids_local & set(response_by_id)):
                central_requirement_id = str(response_by_id[response_item_id].get("requirement_id", "")).strip()
                if central_requirement_id and central_requirement_id not in task_requirement_ids_local:
                    findings.append({"severity": "BLOCKER", "task_id": task_id, "response_item_id": response_item_id, "message": f"任务未同时携带响应口径对应的 requirement_id：{central_requirement_id}"})

    plan_group_ids = collect_ids(plan.get("selected_scoring_group_ids", []), ("scoring_group_id",))
    map_group_ids = collect_ids((scoring_map or {}).get("selected_scoring_group_ids", []), ("scoring_group_id",))
    if map_group_ids and plan_group_ids != map_group_ids:
        findings.append({"severity": "BLOCKER", "message": "章节规划 selected_scoring_group_ids 与评分映射不一致"})

    expected_scoring_ids = extract_scoring_item_ids(scoring_map or {})
    expected_scoring_ids.update(
        str(record.get("score", {}).get("score_item_id", "")).strip()
        for record in records
        if isinstance(record.get("score"), dict) and str(record.get("score", {}).get("score_item_id", "")).strip()
    )
    mapped_scoring_ids = {
        str(item.get("scoring_item_id", "")).strip()
        for item in scoring_item_mappings
        if isinstance(item, dict) and str(item.get("scoring_item_id", "")).strip()
    }
    for section in sections:
        mapped_scoring_ids.update(str(item).strip() for item in section.get("mapped_scoring_item_ids", []) if str(item).strip())
    mapped_scoring_ids.update(task_scoring_item_ids)

    missing_scoring = expected_scoring_ids - mapped_scoring_ids
    if missing_scoring:
        findings.append({"severity": "BLOCKER", "message": f"评分项未映射到章节或任务：{sorted(missing_scoring)}"})
    if expected_scoring_ids and not mapped_scoring_ids:
        findings.append({"severity": "BLOCKER", "message": "存在评分项，但章节规划没有任何评分映射"})
    for scoring_item_id in sorted(expected_scoring_ids):
        mapped_internal_sections = [
            section
            for section in sections
            if section_levels.get(str(section.get("section_id", "")).strip(), 0) >= 2
            and scoring_item_id in {str(item).strip() for item in section.get("mapped_scoring_item_ids", [])}
        ]
        mapped_hierarchy = [
            item
            for item in scoring_item_mappings
            if isinstance(item, dict)
            and str(item.get("scoring_item_id", "")).strip() == scoring_item_id
            and any(
                isinstance(node, dict) and parse_int(node.get("level")) >= 2
                for node in item.get("mapped_section_hierarchy", [])
            )
        ]
        if scoring_item_id in mapped_scoring_ids and not mapped_internal_sections and not mapped_hierarchy:
            findings.append({"severity": "MAJOR", "message": f"评分项 {scoring_item_id} 只映射到一级章节或任务，缺少二级及以下标题承接"})

    expected_score_atom_ids: set[str] = set()
    mapped_score_atom_ids: set[str] = set()
    allowed_response_strategies = {
        "single_primary_only",
        "summary_here_detail_there",
        "detail_here_reference_there",
        "shared_evidence_distinct_focus",
    }
    scoring_mapping_by_id = {
        str(item.get("scoring_item_id", "")).strip(): item
        for item in scoring_item_mappings
        if isinstance(item, dict) and str(item.get("scoring_item_id", "")).strip()
    }
    quality_only_phrases: set[str] = set()
    global_constraint_phrases: set[str] = set()
    response_objects: set[str] = set()

    for scoring_item in scoring_map_items(scoring_map or {}):
        scoring_item_id = str(scoring_item.get("scoring_item_id", "")).strip()
        atoms = scoring_item.get("score_atoms", [])
        if not scoring_item_id or not isinstance(atoms, list) or not atoms:
            continue
        plan_mapping = scoring_mapping_by_id.get(scoring_item_id)
        if not plan_mapping:
            findings.append({"severity": "BLOCKER", "scoring_item_id": scoring_item_id, "message": "评分项缺少 scoring_item_mappings 记录，无法核验评分原文与目录的一一对应"})
            continue

        highest_score_text = str(plan_mapping.get("highest_score_band_text", "")).strip()
        if not highest_score_text:
            findings.append({"severity": "CRITICAL", "scoring_item_id": scoring_item_id, "message": "章节规划未保留最高得分档原文"})

        source_constraints = scoring_item.get("global_constraints", [])
        required_constraint_ids = {
            str(item.get("constraint_id", "")).strip()
            for item in source_constraints
            if isinstance(item, dict) and str(item.get("constraint_id", "")).strip() and item.get("apply_to_all_atoms", True)
        }
        for constraint in source_constraints:
            if isinstance(constraint, dict) and str(constraint.get("original_phrase", "")).strip():
                global_constraint_phrases.add(normalize_label(constraint.get("original_phrase")))

        mapped_constraints = plan_mapping.get("global_constraints", [])
        if not isinstance(mapped_constraints, list):
            mapped_constraints = []
        mapped_constraint_ids = {
            str(item.get("constraint_id", "")).strip()
            for item in mapped_constraints
            if isinstance(item, dict) and str(item.get("constraint_id", "")).strip()
        }
        mapped_constraint_ids.update(
            str(item).strip()
            for item in mapped_constraints
            if not isinstance(item, dict) and str(item).strip()
        )

        atom_mappings = plan_mapping.get("score_atom_mappings", [])
        if not isinstance(atom_mappings, list):
            atom_mappings = []
        atom_mapping_by_id = {
            str(item.get("score_atom_id", "")).strip(): item
            for item in atom_mappings
            if isinstance(item, dict) and str(item.get("score_atom_id", "")).strip()
        }

        for atom in atoms:
            if not isinstance(atom, dict):
                continue
            score_atom_id = str(atom.get("score_atom_id", "")).strip()
            if not score_atom_id:
                continue
            expected_score_atom_ids.add(score_atom_id)
            response_object = str(atom.get("response_object", "")).strip()
            normalized_response_object = normalize_label(response_object)
            if normalized_response_object:
                response_objects.add(normalized_response_object)
            source_quality_values = atom.get("quality_criteria", [])
            if not isinstance(source_quality_values, list):
                source_quality_values = []
            source_quality = {
                normalize_label(item)
                for item in source_quality_values
                if normalize_label(item)
            }
            quality_only_phrases.update(source_quality)

            atom_mapping = atom_mapping_by_id.get(score_atom_id)
            if not atom_mapping:
                findings.append({"severity": "BLOCKER", "scoring_item_id": scoring_item_id, "score_atom_id": score_atom_id, "message": "评分内容对象未建立 score_atom_mappings 记录"})
                continue
            mapped_score_atom_ids.add(score_atom_id)
            primary_section_id = str(atom_mapping.get("primary_section_id", "")).strip()
            primary_section = section_by_id.get(primary_section_id)
            if not primary_section:
                findings.append({"severity": "BLOCKER", "score_atom_id": score_atom_id, "message": f"评分内容对象缺少有效主响应章节：{primary_section_id or '未填写'}"})
                continue
            if section_levels.get(primary_section_id) != 3:
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "section_id": primary_section_id, "message": "评分内容对象的主响应章节必须为三级标题"})

            primary_title = str(primary_section.get("title", "")).strip()
            if atom.get("heading_required", True) and normalized_response_object and normalize_label(primary_title) != normalized_response_object:
                findings.append(
                    {
                        "severity": "CRITICAL",
                        "score_atom_id": score_atom_id,
                        "section_id": primary_section_id,
                        "message": f"三级标题未与评分内容对象逐项对应：应为“{response_object}”，实际为“{primary_title}”",
                    }
                )

            derivation = primary_section.get("scoring_derivation", {})
            if not isinstance(derivation, dict):
                derivation = {}
            derivation_atom_values = derivation.get("score_atom_ids", [])
            if not isinstance(derivation_atom_values, list):
                derivation_atom_values = []
            derivation_atom_ids = {str(item).strip() for item in derivation_atom_values if str(item).strip()}
            if score_atom_id not in derivation_atom_ids:
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "section_id": primary_section_id, "message": "三级标题未回填对应 score_atom_id"})
            if str(derivation.get("mapping_role", "primary")).strip() != "primary":
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "section_id": primary_section_id, "message": "主响应三级标题的 mapping_role 必须为 primary"})
            if not str(derivation.get("highest_score_band_text", "")).strip():
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "section_id": primary_section_id, "message": "三级标题未保留最高得分档拆解依据"})

            atom_mapping_quality = atom_mapping.get("quality_criteria", [])
            derivation_quality = derivation.get("quality_criteria", [])
            if not isinstance(atom_mapping_quality, list):
                atom_mapping_quality = []
            if not isinstance(derivation_quality, list):
                derivation_quality = []
            mapped_quality = {
                normalize_label(item)
                for item in atom_mapping_quality + derivation_quality
                if normalize_label(item)
            }
            if source_quality - mapped_quality:
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": f"质量标准未传入写作约束：{sorted(source_quality - mapped_quality)}"})

            atom_mapping_constraints = atom_mapping.get("global_constraint_ids", [])
            derivation_constraints = derivation.get("global_constraint_ids", [])
            if not isinstance(atom_mapping_constraints, list):
                atom_mapping_constraints = []
            if not isinstance(derivation_constraints, list):
                derivation_constraints = []
            atom_constraint_ids = {
                str(item).strip()
                for item in atom_mapping_constraints + derivation_constraints
                if str(item).strip()
            }
            if required_constraint_ids - (mapped_constraint_ids | atom_constraint_ids):
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": f"全局编写约束未作用到评分内容对象：{sorted(required_constraint_ids - (mapped_constraint_ids | atom_constraint_ids))}"})

            supporting_section_values = atom_mapping.get("supporting_section_ids", [])
            if not isinstance(supporting_section_values, list):
                supporting_section_values = []
            supporting_section_ids = [str(item).strip() for item in supporting_section_values if str(item).strip()]
            response_strategy = str(atom_mapping.get("response_strategy", "single_primary_only")).strip()
            if response_strategy not in allowed_response_strategies:
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": f"未知 response_strategy：{response_strategy}"})
            if supporting_section_ids and response_strategy == "single_primary_only":
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": "存在关联章节时必须声明概述、深化或差异化响应策略"})
            for supporting_section_id in supporting_section_ids:
                if supporting_section_id == primary_section_id:
                    findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": "主响应章节不得同时列为关联章节"})
                elif supporting_section_id not in section_by_id:
                    findings.append({"severity": "BLOCKER", "score_atom_id": score_atom_id, "message": f"关联章节不存在：{supporting_section_id}"})

            primary_atom_sections = []
            for section in sections:
                if not isinstance(section, dict) or section_levels.get(str(section.get("section_id", "")).strip()) != 3:
                    continue
                section_derivation = section.get("scoring_derivation", {})
                if not isinstance(section_derivation, dict):
                    continue
                section_atom_values = section_derivation.get("score_atom_ids", [])
                if not isinstance(section_atom_values, list):
                    section_atom_values = []
                section_atom_ids = {str(item).strip() for item in section_atom_values if str(item).strip()}
                if score_atom_id in section_atom_ids and str(section_derivation.get("mapping_role", "primary")).strip() == "primary":
                    primary_atom_sections.append(section)
            if len(primary_atom_sections) != 1:
                findings.append({"severity": "CRITICAL", "score_atom_id": score_atom_id, "message": f"评分内容对象必须且只能有 1 个三级主响应标题，实际 {len(primary_atom_sections)} 个"})

    for section in sections:
        if not isinstance(section, dict) or section_levels.get(str(section.get("section_id", "")).strip()) != 3:
            continue
        normalized_title = normalize_label(section.get("title", ""))
        if normalized_title and normalized_title not in response_objects and normalized_title in quality_only_phrases:
            findings.append({"severity": "CRITICAL", "section_id": str(section.get("section_id", "")).strip(), "message": "质量程度词不得单独作为三级标题，应转为 writing_quality_criteria"})
        if normalized_title and normalized_title not in response_objects and normalized_title in global_constraint_phrases:
            findings.append({"severity": "CRITICAL", "section_id": str(section.get("section_id", "")).strip(), "message": "全局编写约束不得单独作为三级标题"})

    manual_confirmations = plan.get("manual_confirmations", [])
    if not isinstance(manual_confirmations, list):
        findings.append({"severity": "MAJOR", "message": "manual_confirmations 必须为数组"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities.intersection({"CRITICAL", "MAJOR"}) else "PASS"
    return {
        "status": status,
        "section_count": len(sections),
        "writing_task_count": len(writing_tasks),
        "mapped_requirement_count": len(mapped_requirement_ids & requirement_ids),
        "required_requirement_count": len(mandatory_ids),
        "mapped_scoring_item_count": len(mapped_scoring_ids & expected_scoring_ids) if expected_scoring_ids else len(mapped_scoring_ids),
        "expected_scoring_item_count": len(expected_scoring_ids),
        "mapped_score_atom_count": len(mapped_score_atom_ids & expected_score_atom_ids),
        "expected_score_atom_count": len(expected_score_atom_ids),
        "mapped_response_item_count": len(mapped_response_ids & required_response_ids),
        "required_response_item_count": len(required_response_ids),
        "findings": findings,
    }


def shred_rfp(project_dir: Path, shred_file: Path) -> dict:
    data = load_json(shred_file)
    outputs = data.get("outputs", data)
    output_map = {
        "atomic_requirements": project_dir / "requirements" / "atomic-requirements.json",
        "marker_register": project_dir / "requirements" / "marker-register.json",
        "rejection_clauses": project_dir / "requirements" / "rejection-clauses.json",
        "scoring_applicability": project_dir / "requirements" / "scoring-applicability.json",
        "scoring_map": project_dir / "requirements" / "scoring-map.json",
        "response_register": project_dir / "requirements" / "response-register.json",
        "mandatory_requirements": project_dir / "requirements" / "mandatory-requirements.json",
        "format_rules": project_dir / "requirements" / "format-rules.json",
        "exclusion_list": project_dir / "requirements" / "exclusion-list.json",
    }
    written: list[str] = []
    for key, path in output_map.items():
        if key in outputs:
            write_json(path, outputs[key])
            written.append(str(path.relative_to(project_dir)))

    report = {"status": "PASS", "written": written, "findings": []}
    if not written:
        report["status"] = "REJECT"
        report["findings"].append({"severity": "BLOCKER", "message": "shred 输入未包含任何可写入的 requirements 产物"})
        return report

    atomic_path = output_map["atomic_requirements"]
    marker_path = output_map["marker_register"]
    rejection_path = output_map["rejection_clauses"]
    scoring_map_path = output_map["scoring_map"]
    scoring_applicability_path = output_map["scoring_applicability"]
    response_register_path = output_map["response_register"]
    if atomic_path.exists():
        requirement_report = validate_requirement_register(load_json(atomic_path))
        report["requirements"] = requirement_report
    if marker_path.exists():
        marker_report = validate_marker_register(load_json(marker_path))
        report["marker_register"] = marker_report
    if rejection_path.exists():
        rejection_report = validate_rejection_clauses(load_json(rejection_path))
        report["rejection_clauses"] = rejection_report
    scoring_applicability_data = load_json(scoring_applicability_path) if scoring_applicability_path.exists() else None
    if scoring_map_path.exists():
        report["scoring_map"] = validate_scoring_map(load_json(scoring_map_path), scoring_applicability_data)
    if scoring_applicability_data is not None:
        project = load_json(project_dir / "project.json") if (project_dir / "project.json").exists() else {}
        report["scoring_applicability"] = validate_scoring_applicability(
            scoring_applicability_data,
            str(project.get("package_name", "")),
            load_json(scoring_map_path) if scoring_map_path.exists() else None,
        )
    if response_register_path.exists():
        report["response_register"] = validate_response_register(
            load_json(response_register_path),
            load_json(atomic_path) if atomic_path.exists() else None,
        )
    if atomic_path.exists() and marker_path.exists() and rejection_path.exists():
        report["cross_refs"] = validate_requirement_cross_refs(load_json(atomic_path), load_json(marker_path), load_json(rejection_path))

    statuses = [
        value["status"]
        for value in report.values()
        if isinstance(value, dict) and "status" in value
    ]
    report["status"] = "REJECT" if "REJECT" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS"
    return report


def collect_stage_errors(project_dir: Path, stage: str) -> list[str]:
    errors: list[str] = []
    if stage in {"planning", "grounding", "drafting", "expansion", "integration", "review", "export"}:
        if not (project_dir / "planning" / "chapter-plan.json").exists():
            errors.append("G2 未通过：缺少 planning/chapter-plan.json")
        if not list((project_dir / "tasks").glob("chapter-task-*.json")):
            errors.append("G2 未通过：缺少 tasks/chapter-task-*.json")
    if stage in {"grounding", "drafting", "expansion", "integration", "review", "export"}:
        if not list((project_dir / "grounding").glob("*.json")):
            errors.append("G2 未通过：缺少 grounding/*.json 章节依据包")
        if not list((project_dir / "paragraph-plans").glob("*.json")):
            errors.append("G2 未通过：缺少 paragraph-plans/*.json 段落写作计划")
    if stage in {"drafting", "expansion", "integration", "review", "export"}:
        if not list((project_dir / "chapters").glob("*.md")):
            errors.append("G2/G3 未通过：缺少 chapters/*.md")
        if not list((project_dir / "evidence").glob("*.json")):
            errors.append("G2/G3 未通过：缺少 evidence/*.json")
        if not list((project_dir / "reviews").glob("chapter-draft-*.json")):
            errors.append("G2/G3 未通过：缺少 reviews/chapter-draft-*.json")
    if stage in {"expansion", "integration", "review", "export"}:
        if not list((project_dir / "expanded").glob("*.md")):
            errors.append("G3 未通过：缺少 expanded/*.md")
        if not list((project_dir / "reviews").glob("expansion-*.json")):
            errors.append("G3 未通过：缺少 reviews/expansion-*.json")
    if stage in {"integration", "review", "export"}:
        if not (project_dir / "merged" / "technical-bid-draft.md").exists():
            errors.append("G3 未通过：缺少 merged/technical-bid-draft.md")
        if not (project_dir / "merged" / "traceability.json").exists():
            errors.append("G3 未通过：缺少 merged/traceability.json")
    if stage in {"review", "export"}:
        review_files = [
            "requirements-check.json",
            "response-register-check.json",
            "response-consistency.json",
            "compliance.json",
            "rejection.json",
            "residue.json",
            "format.json",
        ]
        for filename in review_files:
            report_path = project_dir / "reviews" / filename
            if not report_path.exists():
                errors.append(f"G4 未通过：缺少 reviews/{filename}")
            else:
                try:
                    report_status = str(load_json(report_path).get("status", "")).strip().upper()
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"G4 未通过：reviews/{filename} 无法读取：{exc}")
                else:
                    if report_status != "PASS":
                        errors.append(f"G4 未通过：reviews/{filename} 状态为 {report_status or 'UNKNOWN'}")
    return errors


def resolve_project_artifact(project_dir: Path, artifact_ref: object) -> Path | None:
    raw_ref = str(artifact_ref or "").strip()
    if not raw_ref:
        return None
    root = project_dir.resolve()
    candidate = Path(raw_ref)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def report_gate_error(report_path: Path, gate: str) -> str | None:
    if not report_path.exists():
        return f"{gate} 未通过：缺少 {report_path.name} 检查报告"
    try:
        status = str(load_json(report_path).get("status", "")).strip().upper()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"{gate} 未通过：检查报告 {report_path.name} 无法读取：{exc}"
    if status != "PASS":
        return f"{gate} 未通过：检查报告 {report_path.name} 状态为 {status or 'UNKNOWN'}"
    return None


def review_minimalism(workflow: dict, router: dict) -> dict:
    stage_policy = router.get("stage_policy", {})
    anti_patterns = router.get("anti_patterns", [])
    stages = []
    findings = []

    for stage in workflow.get("stages", []):
        stage_id = stage.get("id", "")
        policy = stage_policy.get(stage_id, {})
        configured_level = stage.get("default_execution_level")
        router_level = policy.get("default_level")
        agents = stage.get("agents", [])
        deterministic_checks = stage.get("deterministic_checks", [])
        agents_only_when = stage.get("agents_only_when", "")
        context_policy = stage.get("context_policy", "")

        if router_level and configured_level != router_level:
            findings.append(
                {
                    "severity": "MAJOR",
                    "stage": stage_id,
                    "message": f"阶段默认等级为 {configured_level}，与最小化路由 {router_level} 不一致",
                }
            )
        if configured_level == "L0" and agents and not agents_only_when and stage_id != "export":
            findings.append(
                {
                    "severity": "MAJOR",
                    "stage": stage_id,
                    "message": "L0 阶段配置了默认 agents，但缺少 agents_only_when 升级条件",
                }
            )
        if configured_level in {"L0", "L1"} and stage_id not in {"intake", "export"} and not deterministic_checks:
            findings.append(
                {
                    "severity": "MINOR",
                    "stage": stage_id,
                    "message": "低复杂度阶段建议配置 deterministic_checks",
                }
            )
        if configured_level in {"L2", "L3", "L4"} and not context_policy:
            findings.append(
                {
                    "severity": "MAJOR",
                    "stage": stage_id,
                    "message": "L2+ 阶段必须声明 context_policy，避免向 agent 传递完整历史或大型材料",
                }
            )

        stages.append(
            {
                "id": stage_id,
                "default_execution_level": configured_level,
                "router_level": router_level,
                "agents": agents,
                "deterministic_checks": deterministic_checks,
                "agents_only_when": agents_only_when,
                "context_policy": context_policy,
                "escalate_to_agent_when": policy.get("escalate_to_agent_when", []),
            }
        )

    status = "PASS" if not [item for item in findings if item["severity"] in {"MAJOR", "CRITICAL"}] else "REVIEW_REQUIRED"
    return {
        "status": status,
        "principle": router.get("principle", ""),
        "stage_count": len(stages),
        "stages": stages,
        "anti_patterns": anti_patterns,
        "findings": findings,
    }


def init_project(name: str, package: str) -> Path:
    project_dir = ROOT / "projects" / slugify(name)
    if project_dir.exists():
        raise SystemExit(f"项目目录已存在: {project_dir}")

    project = load_json(PROJECT_TEMPLATE)
    project["project_name"] = name
    project["package_name"] = package
    write_json(project_dir / "project.json", project)

    directories = [
        "sources/tender",
        "sources/technical-specification",
        "sources/historical-reference",
        "sources/supporting-material",
        "state",
        "inventory",
        "requirements",
        "planning",
        "tasks",
        "grounding",
        "paragraph-plans",
        "chapters",
        "expanded",
        "evidence",
        "merged",
        "reviews",
        "output",
    ]
    for directory in directories:
        (project_dir / directory).mkdir(parents=True, exist_ok=True)

    shutil.copy2(WORKFLOW, project_dir / "workflow.snapshot.json")
    shutil.copy2(AGENT_CONTRACTS, project_dir / "agent-contracts.snapshot.json")
    shutil.copy2(MINIMALISM_ROUTER, project_dir / "minimalism-router.snapshot.json")
    shutil.copy2(WORKFLOW_STATE_TEMPLATE, project_dir / "state" / "workflow-state.json")
    return project_dir


def build_plan(project_dir: Path) -> Path:
    project = load_json(project_dir / "project.json")
    workflow = load_json(WORKFLOW)
    contracts = load_json(AGENT_CONTRACTS)
    minimalism = load_json(MINIMALISM_ROUTER)
    plan = {
        "project_name": project["project_name"],
        "package_name": project["package_name"],
        "mode": "subagent",
        "execution_rules": [
            "总控 agent 只负责任务拆解、派发、门禁和汇总",
            "章节初稿生成 agent 必须使用互不重叠的输出文件",
            "审查 agent 独立于编写 agent",
            "高风险问题未清零时阻断 Word 导出",
        ],
        "stages": workflow["stages"],
        "agent_contracts": contracts["agents"],
        "minimalism_router": minimalism,
        "state_handoff": {
            "template": "state/workflow-state.json",
            "mode": minimalism.get("state_handoff", {}).get("mode", "compact-state-and-artifact-refs"),
        },
    }
    output = project_dir / "tasks" / "execution-plan.json"
    write_json(output, plan)
    return output


def validate_task_pipeline(
    project_dir: Path,
    stage: str,
    rejection_data: dict | None,
    response_data: dict | None = None,
    scoring_applicability_data: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    task_files = sorted((project_dir / "tasks").glob("chapter-task-*.json"))
    seen_task_ids: set[str] = set()

    for task_file in task_files:
        task = load_json(task_file)
        task_id = str(task.get("task_id", "")).strip()
        task_label = task_id or task_file.name
        if not task_id:
            errors.append(f"G2 未通过：{task_file.name} 缺少 task_id")
        elif task_id in seen_task_ids:
            errors.append(f"G2 未通过：章节任务 task_id 重复：{task_id}")
        seen_task_ids.add(task_id)

        if scoring_applicability_data is not None:
            selected_group_ids = selected_scoring_group_ids(scoring_applicability_data)
            excluded_group_ids = collect_ids(scoring_applicability_data.get("excluded_scoring_group_ids", []), ("scoring_group_id",))
            task_group_ids = collect_ids(task.get("allowed_scoring_group_ids", []), ("scoring_group_id",))
            if not task_group_ids:
                errors.append(f"G2 未通过：任务 {task_label} 缺少 allowed_scoring_group_ids")
            unknown_group_ids = task_group_ids - selected_group_ids
            if unknown_group_ids:
                errors.append(f"G2 未通过：任务 {task_label} 引用了未选中评分组：{sorted(unknown_group_ids)}")
            blocked_group_ids = task_group_ids & excluded_group_ids
            if blocked_group_ids:
                errors.append(f"G2 未通过：任务 {task_label} 引用了已排除评分组：{sorted(blocked_group_ids)}")

        if response_data is not None:
            response_by_id = {
                str(record.get("response_item_id", "")).strip(): record
                for record in response_register_records(response_data)
                if str(record.get("response_item_id", "")).strip()
            }
            task_requirement_ids_local = collect_ids(task.get("atomic_requirement_ids", []), ("requirement_id",))
            task_requirement_ids_local.update(collect_ids(task.get("requirement_ids", []), ("requirement_id",)))
            task_requirement_ids_local.update(collect_ids(task.get("mandatory_requirements", []), ("requirement_id", "requirement_ids")))
            task_requirement_ids_local.update(collect_ids(task.get("planned_outline", []), ("requirement_id", "requirement_ids")))
            task_response_ids = collect_ids(task.get("response_item_ids", []), ("response_item_id",))
            if parse_int(task.get("version"), 1) >= 2 and task_requirement_ids_local and not task_response_ids:
                errors.append(f"G2 未通过：任务 {task_label} 包含技术要求但顶层缺少 response_item_ids")
            for response_item_id in sorted(task_response_ids):
                record = response_by_id.get(response_item_id)
                if record is None:
                    errors.append(f"G2 未通过：任务 {task_label} 引用了未登记响应口径 {response_item_id}")
                elif str(record.get("status", "")).upper() != "CONFIRMED" or not record.get("human_confirmed"):
                    errors.append(f"G2 未通过：任务 {task_label} 引用了未确认响应口径 {response_item_id}")
                elif str(record.get("response_mode", "")).upper() == "NO_DRAFT":
                    errors.append(f"G2 未通过：任务 {task_label} 引用了禁止写入正文的响应口径 {response_item_id}")
                else:
                    requirement_id = str(record.get("requirement_id", "")).strip()
                    if requirement_id and requirement_id not in task_requirement_ids_local:
                        errors.append(f"G2 未通过：任务 {task_label} 未同时携带响应口径 {response_item_id} 对应的 requirement_id：{requirement_id}")

        grounding_path = resolve_project_artifact(project_dir, task.get("grounding_pack_file"))
        paragraph_plan_path = resolve_project_artifact(project_dir, task.get("paragraph_plan_file"))
        if grounding_path is None:
            errors.append(f"G2 未通过：任务 {task_label} 缺少有效 grounding_pack_file，或路径越出项目目录")
        elif not grounding_path.exists():
            errors.append(f"G2 未通过：任务 {task_label} 的章节依据包不存在：{grounding_path.name}")
        if paragraph_plan_path is None:
            errors.append(f"G2 未通过：任务 {task_label} 缺少有效 paragraph_plan_file，或路径越出项目目录")
        elif not paragraph_plan_path.exists():
            errors.append(f"G2 未通过：任务 {task_label} 的段落写作计划不存在：{paragraph_plan_path.name}")

        grounding_pack = load_json(grounding_path) if grounding_path and grounding_path.exists() else None
        paragraph_plan = load_json(paragraph_plan_path) if paragraph_plan_path and paragraph_plan_path.exists() else None
        if grounding_pack is not None:
            if str(grounding_pack.get("task_id", "")).strip() != task_id:
                errors.append(f"G2 未通过：任务 {task_label} 与章节依据包 task_id 不一致")
            grounding_report = validate_grounding_pack(
                grounding_pack,
                response_data,
                scoring_applicability_data,
            )
            if grounding_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：任务 {task_label} 的章节依据包状态为 {grounding_report['status']}，"
                    f"发现 {len(grounding_report['findings'])} 个问题"
                )

            task_scoring_ids = collect_ids(task, ("scoring_item_id", "scoring_item_ids"))
            grounded_scoring_ids = collect_ids(grounding_pack, ("scoring_item_id", "scoring_item_ids"))
            missing_scoring_ids = task_scoring_ids - grounded_scoring_ids
            if missing_scoring_ids:
                errors.append(f"G2 未通过：任务 {task_label} 的评分项未全部进入章节依据包：{sorted(missing_scoring_ids)}")

            task_requirement_ids = collect_ids(task, ("requirement_id", "requirement_ids", "atomic_requirement_ids"))
            grounded_requirement_ids = collect_ids(grounding_pack, ("requirement_id", "requirement_ids"))
            missing_requirement_ids = task_requirement_ids - grounded_requirement_ids
            if missing_requirement_ids:
                errors.append(f"G2 未通过：任务 {task_label} 的技术要求未全部进入章节依据包：{sorted(missing_requirement_ids)}")

            task_response_ids = collect_ids(task, ("response_item_id", "response_item_ids"))
            grounded_response_ids = collect_ids(grounding_pack.get("response_refs", []), ("response_item_id", "response_item_ids"))
            missing_response_ids = task_response_ids - grounded_response_ids
            if missing_response_ids:
                errors.append(f"G2 未通过：任务 {task_label} 的响应口径未全部进入章节依据包：{sorted(missing_response_ids)}")

            task_group_ids = collect_ids(task.get("allowed_scoring_group_ids", []), ("scoring_group_id",))
            grounded_group_ids = collect_ids(grounding_pack.get("allowed_scoring_group_ids", []), ("scoring_group_id",))
            if task_group_ids and grounded_group_ids != task_group_ids:
                errors.append(f"G2 未通过：任务 {task_label} 与章节依据包的评分组边界不一致")

            task_rejection_ids = collect_ids(task, ("rejection_clause_id", "rejection_clause_ids"))
            grounded_rejection_ids = collect_ids(grounding_pack, ("rejection_clause_id", "rejection_clause_ids"))
            missing_rejection_ids = task_rejection_ids - grounded_rejection_ids
            if missing_rejection_ids:
                errors.append(f"G2 未通过：任务 {task_label} 的废标/否决条款未全部进入章节依据包：{sorted(missing_rejection_ids)}")

        if paragraph_plan is not None:
            paragraph_report = validate_paragraph_plan(paragraph_plan, grounding_pack)
            if paragraph_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：任务 {task_label} 的段落写作计划状态为 {paragraph_report['status']}，"
                    f"发现 {len(paragraph_report['findings'])} 个问题"
                )

        if stage not in {"drafting", "expansion", "integration", "review", "export"}:
            continue

        handoff = task.get("expansion_handoff", {}) if isinstance(task.get("expansion_handoff"), dict) else {}
        draft_path = resolve_project_artifact(project_dir, task.get("output_file"))
        evidence_path = resolve_project_artifact(project_dir, task.get("evidence_file") or handoff.get("evidence_file"))
        draft_review_path = resolve_project_artifact(project_dir, task.get("draft_review_file"))
        if draft_path is None:
            errors.append(f"G3 未通过：任务 {task_label} 缺少有效 output_file")
        elif not draft_path.exists():
            errors.append(f"G3 未通过：任务 {task_label} 的章节初稿不存在：{draft_path.name}")
        if evidence_path is None:
            errors.append(f"G3 未通过：任务 {task_label} 缺少有效 evidence_file")
        elif not evidence_path.exists():
            errors.append(f"G3 未通过：任务 {task_label} 的 evidence 文件不存在：{evidence_path.name}")
        if draft_review_path is None:
            errors.append(f"G3 未通过：任务 {task_label} 缺少有效 draft_review_file")
        else:
            review_error = report_gate_error(draft_review_path, "G3")
            if review_error:
                errors.append(review_error)

        evidence_data = load_json(evidence_path) if evidence_path and evidence_path.exists() else None
        if draft_path and draft_path.exists():
            draft_text = draft_path.read_text(encoding="utf-8-sig")
            draft_report = validate_chapter_draft(task, draft_text, evidence_data, grounding_pack, paragraph_plan)
            if draft_report["status"] != "PASS":
                errors.append(
                    f"G3 未通过：任务 {task_label} 的章节初稿状态为 {draft_report['status']}，"
                    f"发现 {len(draft_report['findings'])} 个问题"
                )
            if rejection_data is not None:
                rejection_report = validate_rejection_content(rejection_data, draft_text, task, evidence_data)
                if rejection_report["status"] != "PASS":
                    errors.append(
                        f"G3 未通过：任务 {task_label} 的章节初稿废标/否决检查状态为 {rejection_report['status']}，"
                        f"发现 {len(rejection_report['findings'])} 个问题"
                    )
            if response_data is not None:
                response_report = validate_response_content(response_data, draft_text, task, evidence_data)
                if response_report["status"] != "PASS":
                    errors.append(
                        f"G3 未通过：任务 {task_label} 的我司响应口径检查状态为 {response_report['status']}，"
                        f"发现 {len(response_report['findings'])} 个问题"
                    )

        if stage not in {"expansion", "integration", "review", "export"}:
            continue

        expansion_task_path = resolve_project_artifact(project_dir, handoff.get("expansion_task_file"))
        if expansion_task_path is None:
            errors.append(f"G3 未通过：任务 {task_label} 缺少有效 expansion_task_file")
            continue
        if not expansion_task_path.exists():
            errors.append(f"G3 未通过：任务 {task_label} 的扩写任务书不存在：{expansion_task_path.name}")
            continue

        expansion_task = load_json(expansion_task_path)
        expanded_path = resolve_project_artifact(project_dir, expansion_task.get("output_file"))
        expansion_review_path = resolve_project_artifact(project_dir, expansion_task.get("review_file"))
        if expanded_path is None:
            errors.append(f"G3 未通过：扩写任务 {task_label} 缺少有效 output_file")
        elif not expanded_path.exists():
            errors.append(f"G3 未通过：任务 {task_label} 的扩写稿不存在：{expanded_path.name}")
        if expansion_review_path is None:
            errors.append(f"G3 未通过：扩写任务 {task_label} 缺少有效 review_file")
        else:
            review_error = report_gate_error(expansion_review_path, "G3")
            if review_error:
                errors.append(review_error)

        if draft_path and draft_path.exists() and expanded_path and expanded_path.exists():
            source_text = draft_path.read_text(encoding="utf-8-sig")
            expanded_text = expanded_path.read_text(encoding="utf-8-sig")
            expansion_report = validate_expansion(source_text, expanded_text, evidence_data, paragraph_plan)
            if expansion_report["status"] != "PASS":
                errors.append(
                    f"G3 未通过：任务 {task_label} 的扩写稿状态为 {expansion_report['status']}，"
                    f"发现 {len(expansion_report['findings'])} 个问题"
                )
            if rejection_data is not None:
                rejection_report = validate_rejection_content(rejection_data, expanded_text, task, evidence_data)
                if rejection_report["status"] != "PASS":
                    errors.append(
                        f"G3 未通过：任务 {task_label} 的扩写稿废标/否决检查状态为 {rejection_report['status']}，"
                        f"发现 {len(rejection_report['findings'])} 个问题"
                    )
            if response_data is not None:
                response_report = validate_response_content(response_data, expanded_text, task, evidence_data)
                if response_report["status"] != "PASS":
                    errors.append(
                        f"G3 未通过：任务 {task_label} 的扩写稿响应口径检查状态为 {response_report['status']}，"
                        f"发现 {len(response_report['findings'])} 个问题"
                    )
    return errors


def validate_project(project_dir: Path, stage: str = "export") -> list[str]:
    errors: list[str] = []
    project_path = project_dir / "project.json"
    if not project_path.exists():
        return [f"缺少项目清单: {project_path}"]

    project = load_json(project_path)
    if not project.get("project_name"):
        errors.append("project_name 未填写")
    if not project.get("package_name"):
        errors.append("package_name 未填写")
    if not project.get("package_confirmed"):
        errors.append("G0 未通过：当前标包尚未人工确认")
    if not project.get("document_format_confirmed"):
        errors.append("G0 未通过：技术文件格式尚未人工确认")

    source_groups = project.get("sources", {})
    if not source_groups.get("tender"):
        errors.append("缺少招标文件来源登记")
    if not source_groups.get("technical_specification"):
        errors.append("缺少技术规范书来源登记")

    source_readiness = project_dir / "inventory" / "source-readiness.json"
    if not source_readiness.exists():
        errors.append("G0 未通过：缺少 inventory/source-readiness.json")
    else:
        source_report = validate_source_readiness(load_json(source_readiness))
        if source_report["status"] != "PASS":
            errors.append(
                f"G0 未通过：资料可读性检查结果为 {source_report['status']}，"
                f"发现 {len(source_report['findings'])} 个问题"
            )

    scoring_map = project_dir / "requirements" / "scoring-map.json"
    atomic_requirements = project_dir / "requirements" / "atomic-requirements.json"
    marker_register = project_dir / "requirements" / "marker-register.json"
    rejection_clauses = project_dir / "requirements" / "rejection-clauses.json"
    scoring_applicability = project_dir / "requirements" / "scoring-applicability.json"
    response_register = project_dir / "requirements" / "response-register.json"
    exclusion_list = project_dir / "requirements" / "exclusion-list.json"
    requirement_data = None
    marker_data = None
    rejection_data = None
    response_data = None
    scoring_map_data = load_json(scoring_map) if scoring_map.exists() else None
    scoring_applicability_data = load_json(scoring_applicability) if scoring_applicability.exists() else None
    if not atomic_requirements.exists():
        errors.append("G1 未通过：缺少 requirements/atomic-requirements.json")
    else:
        requirement_data = load_json(atomic_requirements)
        requirement_report = validate_requirement_register(requirement_data)
        if requirement_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：原子要点台账检查结果为 {requirement_report['status']}，"
                f"发现 {len(requirement_report['findings'])} 个问题"
            )
    if not marker_register.exists():
        errors.append("G1 未通过：缺少 requirements/marker-register.json")
    else:
        marker_data = load_json(marker_register)
        marker_report = validate_marker_register(marker_data)
        if marker_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：特殊标记台账检查结果为 {marker_report['status']}，"
                f"发现 {len(marker_report['findings'])} 个问题"
            )
    if not rejection_clauses.exists():
        errors.append("G1 未通过：缺少 requirements/rejection-clauses.json")
    else:
        rejection_data = load_json(rejection_clauses)
        rejection_report = validate_rejection_clauses(rejection_data)
        if rejection_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：废标/否决条款检查结果为 {rejection_report['status']}，"
                f"发现 {len(rejection_report['findings'])} 个问题"
            )
    if requirement_data is not None and marker_data is not None and rejection_data is not None:
        cross_ref_report = validate_requirement_cross_refs(requirement_data, marker_data, rejection_data)
        if cross_ref_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：要求台账交叉引用检查结果为 {cross_ref_report['status']}，"
                f"发现 {len(cross_ref_report['findings'])} 个问题"
            )
    if not scoring_applicability.exists():
        errors.append("G1 未通过：缺少 requirements/scoring-applicability.json")
    else:
        scoring_applicability_report = validate_scoring_applicability(
            scoring_applicability_data or {},
            project.get("package_name", ""),
            scoring_map_data,
        )
        if scoring_applicability_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：评分适用范围检查结果为 {scoring_applicability_report['status']}，"
                f"发现 {len(scoring_applicability_report['findings'])} 个问题"
            )
    if not scoring_map.exists():
        errors.append("G1 未通过：缺少 requirements/scoring-map.json")
    else:
        scoring_map_report = validate_scoring_map(scoring_map_data or {}, scoring_applicability_data)
        if scoring_map_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：评分最高档原子化检查结果为 {scoring_map_report['status']}，"
                f"发现 {len(scoring_map_report['findings'])} 个问题"
            )
    if not response_register.exists():
        errors.append("G1 未通过：缺少 requirements/response-register.json")
    else:
        response_data = load_json(response_register)
        response_report = validate_response_register(response_data, requirement_data)
        if response_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：要求—响应口径台账检查结果为 {response_report['status']}，"
                f"发现 {len(response_report['findings'])} 个问题"
            )
    if not exclusion_list.exists():
        errors.append("G1 未通过：缺少 requirements/exclusion-list.json")

    if stage in {"planning", "grounding", "drafting", "expansion", "integration", "review", "export"}:
        chapter_plan = project_dir / "planning" / "chapter-plan.json"
        if chapter_plan.exists() and atomic_requirements.exists():
            plan_report = validate_chapter_plan(
                load_json(chapter_plan),
                load_json(atomic_requirements),
                scoring_map_data or {},
                response_data,
            )
            if plan_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：章节规划检查结果为 {plan_report['status']}，"
                    f"发现 {len(plan_report['findings'])} 个问题"
                )
    if stage in {"grounding", "drafting", "expansion", "integration", "review", "export"}:
        for grounding_file in sorted((project_dir / "grounding").glob("*.json")):
            grounding_report = validate_grounding_pack(
                load_json(grounding_file),
                response_data,
                scoring_applicability_data,
            )
            if grounding_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：章节依据包 {grounding_file.name} 检查结果为 {grounding_report['status']}，"
                    f"发现 {len(grounding_report['findings'])} 个问题"
                )
        grounding_by_task: dict[str, dict] = {}
        for path in sorted((project_dir / "grounding").glob("*.json")):
            grounding_data = load_json(path)
            grounding_task_id = str(grounding_data.get("task_id", "")).strip()
            if grounding_task_id:
                grounding_by_task[grounding_task_id] = grounding_data
        for paragraph_plan_file in sorted((project_dir / "paragraph-plans").glob("*.json")):
            paragraph_plan_data = load_json(paragraph_plan_file)
            paragraph_report = validate_paragraph_plan(
                paragraph_plan_data,
                grounding_by_task.get(str(paragraph_plan_data.get("task_id", "")).strip()),
            )
            if paragraph_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：段落写作计划 {paragraph_plan_file.name} 检查结果为 {paragraph_report['status']}，"
                    f"发现 {len(paragraph_report['findings'])} 个问题"
                )

        errors.extend(
            validate_task_pipeline(
                project_dir,
                stage,
                rejection_data,
                response_data,
                scoring_applicability_data,
            )
        )

    if stage in {"integration", "review", "export"} and rejection_data is not None:
        merged_path = project_dir / "merged" / "technical-bid-draft.md"
        if merged_path.exists():
            merged_rejection_report = validate_rejection_content(
                rejection_data,
                merged_path.read_text(encoding="utf-8-sig"),
            )
            if merged_rejection_report["status"] != "PASS":
                errors.append(
                    f"G4 未通过：合稿废标/否决检查状态为 {merged_rejection_report['status']}，"
                    f"发现 {len(merged_rejection_report['findings'])} 个问题"
                )
            if response_data is not None:
                merged_response_report = validate_response_content(
                    response_data,
                    merged_path.read_text(encoding="utf-8-sig"),
                )
                if merged_response_report["status"] != "PASS":
                    errors.append(
                        f"G4 未通过：合稿响应口径检查状态为 {merged_response_report['status']}，"
                        f"发现 {len(merged_response_report['findings'])} 个问题"
                    )

    export = project.get("export", {})
    if export.get("high_risk_open", 0) > 0:
        errors.append("G4 未通过：仍有高风险问题，禁止导出")
    if not export.get("draft_only", True):
        errors.append("导出配置必须保持 draft_only=true")
    errors.extend(collect_stage_errors(project_dir, stage))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="技术标 subagent 工作流辅助工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化项目工作区")
    init_parser.add_argument("name")
    init_parser.add_argument("--package", default="")

    plan_parser = subparsers.add_parser("plan", help="生成 subagent 执行计划")
    plan_parser.add_argument("project_dir", type=Path)

    ingest_parser = subparsers.add_parser("ingest-sources", help="解析 PDF/DOCX/XLSX/TXT 来源并生成资料索引和可读性台账")
    ingest_parser.add_argument("project_dir", type=Path)
    ingest_parser.add_argument("--report", type=Path)

    validate_parser = subparsers.add_parser("validate", help="检查阶段门禁")
    validate_parser.add_argument("project_dir", type=Path)
    validate_parser.add_argument(
        "--stage",
        choices=["requirements", "planning", "grounding", "drafting", "expansion", "integration", "review", "export"],
        default="export",
    )

    expansion_parser = subparsers.add_parser("check-expansion", help="检查扩写结构、比例、禁用词、空话和无来源承诺")
    expansion_parser.add_argument("source_file", type=Path)
    expansion_parser.add_argument("expanded_file", type=Path)
    expansion_parser.add_argument("--evidence", type=Path, required=True)
    expansion_parser.add_argument("--paragraph-plan", type=Path, required=True)
    expansion_parser.add_argument("--report", type=Path)

    shred_parser = subparsers.add_parser("shred-rfp", help="落盘并校验 RFP/招标文件拆解产物")
    shred_parser.add_argument("project_dir", type=Path)
    shred_parser.add_argument("shred_file", type=Path)
    shred_parser.add_argument("--report", type=Path)

    requirements_parser = subparsers.add_parser("check-requirements", help="检查逐条原子要点、标记及废标/否决条款")
    requirements_parser.add_argument("requirements_file", type=Path)
    requirements_parser.add_argument("--markers", type=Path)
    requirements_parser.add_argument("--rejections", type=Path)
    requirements_parser.add_argument("--report", type=Path)

    plan_check_parser = subparsers.add_parser("check-plan", help="检查章节规划对原子要点、评分项和写作任务的覆盖")
    plan_check_parser.add_argument("chapter_plan_file", type=Path)
    plan_check_parser.add_argument("--requirements", type=Path, required=True)
    plan_check_parser.add_argument("--scoring-map", type=Path)
    plan_check_parser.add_argument("--response-register", type=Path)
    plan_check_parser.add_argument("--report", type=Path)

    grounding_parser = subparsers.add_parser("check-grounding-pack", help="检查章节依据包是否绑定评分、项目事实、来源和禁用承诺")
    grounding_parser.add_argument("grounding_pack_file", type=Path)
    grounding_parser.add_argument("--response-register", type=Path)
    grounding_parser.add_argument("--scoring-applicability", type=Path)
    grounding_parser.add_argument("--report", type=Path)

    paragraph_plan_parser = subparsers.add_parser("check-paragraph-plan", help="检查段落写作计划是否具备对象、动作、节点、交付物和来源")
    paragraph_plan_parser.add_argument("paragraph_plan_file", type=Path)
    paragraph_plan_parser.add_argument("--grounding", type=Path, required=True)
    paragraph_plan_parser.add_argument("--report", type=Path)

    chapter_draft_parser = subparsers.add_parser("check-chapter-draft", help="检查章节初稿是否按任务书标题树、评分项和证据链真实落位")
    chapter_draft_parser.add_argument("task_file", type=Path)
    chapter_draft_parser.add_argument("draft_file", type=Path)
    chapter_draft_parser.add_argument("--evidence", type=Path, required=True)
    chapter_draft_parser.add_argument("--grounding", type=Path, required=True)
    chapter_draft_parser.add_argument("--paragraph-plan", type=Path, required=True)
    chapter_draft_parser.add_argument("--report", type=Path)

    rejection_parser = subparsers.add_parser("check-rejection", help="检查正文是否触发废标/否决风险")
    rejection_parser.add_argument("rejection_file", type=Path)
    rejection_parser.add_argument("content_file", type=Path)
    rejection_parser.add_argument("--task", type=Path)
    rejection_parser.add_argument("--evidence", type=Path)
    rejection_parser.add_argument("--report", type=Path)

    response_register_parser = subparsers.add_parser("check-response-register", help="检查招标要求到我司响应口径的转换、固定要素和确认状态")
    response_register_parser.add_argument("response_register_file", type=Path)
    response_register_parser.add_argument("--requirements", type=Path)
    response_register_parser.add_argument("--report", type=Path)

    response_content_parser = subparsers.add_parser("check-responses", help="检查正文是否使用已确认的我司响应口径且未改变条件、范围和数值")
    response_content_parser.add_argument("response_register_file", type=Path)
    response_content_parser.add_argument("content_file", type=Path)
    response_content_parser.add_argument("--task", type=Path)
    response_content_parser.add_argument("--evidence", type=Path)
    response_content_parser.add_argument("--report", type=Path)

    sources_parser = subparsers.add_parser("check-sources", help="检查资料可读性、转换状态和关键文件类型")
    sources_parser.add_argument("source_readiness_file", type=Path)
    sources_parser.add_argument("--report", type=Path)

    scoring_parser = subparsers.add_parser("check-scoring-applicability", help="检查评分标准适用标包范围")
    scoring_parser.add_argument("scoring_applicability_file", type=Path)
    scoring_parser.add_argument("--package", required=True)
    scoring_parser.add_argument("--scoring-map", type=Path)
    scoring_parser.add_argument("--report", type=Path)

    scoring_map_parser = subparsers.add_parser("check-scoring-map", help="检查评分最高档原文、评分内容对象、质量标准和全局约束的原子化结果")
    scoring_map_parser.add_argument("scoring_map_file", type=Path)
    scoring_map_parser.add_argument("--applicability", type=Path)
    scoring_map_parser.add_argument("--report", type=Path)

    minimalism_parser = subparsers.add_parser("review-minimalism", help="复盘工作流是否遵循最小充分 agent 原则")
    minimalism_parser.add_argument("--report", type=Path)

    args = parser.parse_args()
    if args.command == "init":
        path = init_project(args.name, args.package)
        print(f"已初始化: {path}")
        return 0
    if args.command == "plan":
        path = build_plan(args.project_dir.resolve())
        print(f"已生成: {path}")
        return 0
    if args.command == "ingest-sources":
        report = ingest_sources(args.project_dir.resolve())
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-expansion":
        report = validate_expansion(
            args.source_file.read_text(encoding="utf-8"),
            args.expanded_file.read_text(encoding="utf-8"),
            load_json(args.evidence) if args.evidence else None,
            load_json(args.paragraph_plan) if args.paragraph_plan else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "shred-rfp":
        report = shred_rfp(args.project_dir.resolve(), args.shred_file.resolve())
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-requirements":
        requirement_data = load_json(args.requirements_file)
        report = validate_requirement_register(requirement_data)
        if args.markers:
            marker_report = validate_marker_register(load_json(args.markers))
            report["marker_register"] = marker_report
        if args.rejections:
            rejection_report = validate_rejection_clauses(load_json(args.rejections))
            report["rejection_clauses"] = rejection_report
        if args.markers and args.rejections:
            cross_ref_report = validate_requirement_cross_refs(
                requirement_data,
                load_json(args.markers),
                load_json(args.rejections),
            )
            report["cross_refs"] = cross_ref_report
            statuses = {
                report["status"],
                report["marker_register"]["status"],
                report["rejection_clauses"]["status"],
                report["cross_refs"]["status"],
            }
            report["status"] = "REJECT" if "REJECT" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS"
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-plan":
        scoring_map_data = load_json(args.scoring_map) if args.scoring_map else {}
        report = validate_chapter_plan(
            load_json(args.chapter_plan_file),
            load_json(args.requirements),
            scoring_map_data,
            load_json(args.response_register) if args.response_register else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-grounding-pack":
        report = validate_grounding_pack(
            load_json(args.grounding_pack_file),
            load_json(args.response_register) if args.response_register else None,
            load_json(args.scoring_applicability) if args.scoring_applicability else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-paragraph-plan":
        report = validate_paragraph_plan(
            load_json(args.paragraph_plan_file),
            load_json(args.grounding) if args.grounding else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-chapter-draft":
        evidence_data = load_json(args.evidence) if args.evidence else None
        report = validate_chapter_draft(
            load_json(args.task_file),
            args.draft_file.read_text(encoding="utf-8"),
            evidence_data,
            load_json(args.grounding) if args.grounding else None,
            load_json(args.paragraph_plan) if args.paragraph_plan else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-rejection":
        report = validate_rejection_content(
            load_json(args.rejection_file),
            args.content_file.read_text(encoding="utf-8"),
            load_json(args.task) if args.task else None,
            load_json(args.evidence) if args.evidence else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-response-register":
        report = validate_response_register(
            load_json(args.response_register_file),
            load_json(args.requirements) if args.requirements else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-responses":
        report = validate_response_content(
            load_json(args.response_register_file),
            args.content_file.read_text(encoding="utf-8-sig"),
            load_json(args.task) if args.task else None,
            load_json(args.evidence) if args.evidence else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-sources":
        report = validate_source_readiness(load_json(args.source_readiness_file))
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-scoring-applicability":
        report = validate_scoring_applicability(
            load_json(args.scoring_applicability_file),
            args.package,
            load_json(args.scoring_map) if args.scoring_map else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "check-scoring-map":
        report = validate_scoring_map(
            load_json(args.scoring_map_file),
            load_json(args.applicability) if args.applicability else None,
        )
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "review-minimalism":
        report = review_minimalism(load_json(WORKFLOW), load_json(MINIMALISM_ROUTER))
        if args.report:
            write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1

    errors = validate_project(args.project_dir.resolve(), stage=args.stage)
    if errors:
        print("门禁检查未通过：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("门禁检查通过，可进入 Word 初稿导出阶段。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
