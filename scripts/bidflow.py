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


def validate_expansion(source: str, expanded: str) -> dict:
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

    return {
        "status": "PASS" if not findings else "REVIEW_REQUIRED",
        "total_length_ratio": round(total_ratio, 2),
        "paragraph_length_ratios": paragraph_ratios,
        "structure_matches": len(source_blocks) == len(expanded_blocks) and source_headings == expanded_headings,
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


def validate_scoring_applicability(data: dict, package_name: str) -> dict:
    findings: list[dict] = []
    groups = data.get("scoring_groups")
    if not isinstance(groups, list) or not groups:
        return {
            "status": "REJECT",
            "selected_group_count": 0,
            "findings": [{"severity": "BLOCKER", "message": "评分适用范围台账 scoring_groups 为空或不存在"}],
        }

    selected = []
    for index, group in enumerate(groups, start=1):
        group_id = str(group.get("scoring_group_id", "")).strip() or f"第 {index} 组"
        source = group.get("source", {})
        applies_to = group.get("applies_to_packages", [])
        if not isinstance(applies_to, list):
            findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": "applies_to_packages 必须为数组"})
            applies_to = []
        if not isinstance(source, dict) or not str(source.get("original_scope_text", "")).strip():
            findings.append({"severity": "CRITICAL", "scoring_group_id": group_id, "message": "缺少评分标准适用范围原文"})
        if group.get("selected_for_current_package"):
            selected.append(group)
            if not label_matches(package_name, applies_to):
                findings.append(
                    {
                        "severity": "BLOCKER",
                        "scoring_group_id": group_id,
                        "message": "选中的评分组未声明适用于当前标包",
                    }
                )
            if not group.get("human_confirmed"):
                findings.append({"severity": "BLOCKER", "scoring_group_id": group_id, "message": "选中评分组尚未人工确认"})

    if len(selected) != 1:
        findings.append({"severity": "BLOCKER", "message": f"当前标包必须且只能选中 1 组评分标准，实际 {len(selected)} 组"})

    severities = {item["severity"] for item in findings}
    status = "REJECT" if "BLOCKER" in severities else "REVIEW_REQUIRED" if severities else "PASS"
    return {"status": status, "selected_group_count": len(selected), "findings": findings}


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


def validate_chapter_plan(plan: dict, requirements: dict, scoring_map: dict | None = None) -> dict:
    findings: list[dict] = []
    sections = plan.get("sections")
    writing_tasks = plan.get("writing_tasks")
    scoring_item_mappings = plan.get("scoring_item_mappings", [])
    technical_requirement_mappings = plan.get("technical_requirement_mappings", [])

    if not isinstance(sections, list) or not sections:
        findings.append({"severity": "BLOCKER", "message": "章节规划 sections 为空或不存在"})
        sections = []
    if not isinstance(writing_tasks, list) or not writing_tasks:
        findings.append({"severity": "BLOCKER", "message": "章节规划 writing_tasks 为空或不存在"})
        writing_tasks = []

    section_ids: set[str] = set()
    task_ids: set[str] = set()
    task_outputs: set[str] = set()
    section_orders: list[int] = []

    for index, section in enumerate(sections, start=1):
        section_id = str(section.get("section_id", "")).strip()
        label = section_id or f"第 {index} 节"
        if not section_id:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少 section_id"})
        elif section_id in section_ids:
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "section_id 重复"})
        section_ids.add(section_id)

        if not str(section.get("title", "")).strip():
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少章节标题"})
        if not section.get("locked_by_tender_format"):
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "章节未声明由招标格式锁定"})
        source = section.get("source", {})
        if not isinstance(source, dict) or not str(source.get("file", "")).strip():
            findings.append({"severity": "CRITICAL", "section_id": label, "message": "缺少格式来源文件"})
        if not isinstance(source, dict) or not str(source.get("original_text", "")).strip():
            findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少格式来源原文"})
        order = section.get("order")
        if isinstance(order, int):
            section_orders.append(order)
        else:
            findings.append({"severity": "MAJOR", "section_id": label, "message": "缺少数字型 order"})

        for task_id in section.get("writing_task_ids", []):
            if str(task_id).strip():
                task_ids.add(str(task_id).strip())

    if section_orders and section_orders != sorted(section_orders):
        findings.append({"severity": "MAJOR", "message": "章节 order 不是递增顺序"})

    writing_task_ids: set[str] = set()
    task_requirement_ids: set[str] = set()
    task_scoring_item_ids: set[str] = set()
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
    if atomic_path.exists():
        requirement_report = validate_requirement_register(load_json(atomic_path))
        report["requirements"] = requirement_report
    if marker_path.exists():
        marker_report = validate_marker_register(load_json(marker_path))
        report["marker_register"] = marker_report
    if rejection_path.exists():
        rejection_report = validate_rejection_clauses(load_json(rejection_path))
        report["rejection_clauses"] = rejection_report
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
    if stage in {"planning", "drafting", "expansion", "integration", "review", "export"}:
        if not (project_dir / "planning" / "chapter-plan.json").exists():
            errors.append("G2 未通过：缺少 planning/chapter-plan.json")
        if not list((project_dir / "tasks").glob("chapter-task-*.json")):
            errors.append("G2 未通过：缺少 tasks/chapter-task-*.json")
    if stage in {"drafting", "expansion", "integration", "review", "export"}:
        if not list((project_dir / "chapters").glob("*.md")):
            errors.append("G2/G3 未通过：缺少 chapters/*.md")
        if not list((project_dir / "evidence").glob("*.json")):
            errors.append("G2/G3 未通过：缺少 evidence/*.json")
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
            "compliance.json",
            "residue.json",
            "format.json",
        ]
        for filename in review_files:
            if not (project_dir / "reviews" / filename).exists():
                errors.append(f"G4 未通过：缺少 reviews/{filename}")
    return errors


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
            "章节编写 agent 必须使用互不重叠的输出文件",
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
    exclusion_list = project_dir / "requirements" / "exclusion-list.json"
    requirement_data = None
    marker_data = None
    rejection_data = None
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
    if not scoring_map.exists():
        errors.append("G1 未通过：缺少 requirements/scoring-map.json")
    if not scoring_applicability.exists():
        errors.append("G1 未通过：缺少 requirements/scoring-applicability.json")
    else:
        scoring_applicability_report = validate_scoring_applicability(load_json(scoring_applicability), project.get("package_name", ""))
        if scoring_applicability_report["status"] != "PASS":
            errors.append(
                f"G1 未通过：评分适用范围检查结果为 {scoring_applicability_report['status']}，"
                f"发现 {len(scoring_applicability_report['findings'])} 个问题"
            )
    if not exclusion_list.exists():
        errors.append("G1 未通过：缺少 requirements/exclusion-list.json")

    if stage in {"planning", "drafting", "expansion", "integration", "review", "export"}:
        chapter_plan = project_dir / "planning" / "chapter-plan.json"
        if chapter_plan.exists() and atomic_requirements.exists():
            scoring_map_data = load_json(scoring_map) if scoring_map.exists() else {}
            plan_report = validate_chapter_plan(load_json(chapter_plan), load_json(atomic_requirements), scoring_map_data)
            if plan_report["status"] != "PASS":
                errors.append(
                    f"G2 未通过：章节规划检查结果为 {plan_report['status']}，"
                    f"发现 {len(plan_report['findings'])} 个问题"
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
        choices=["requirements", "planning", "drafting", "expansion", "integration", "review", "export"],
        default="export",
    )

    expansion_parser = subparsers.add_parser("check-expansion", help="检查扩写稿结构、比例及总结式首尾")
    expansion_parser.add_argument("source_file", type=Path)
    expansion_parser.add_argument("expanded_file", type=Path)
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
    plan_check_parser.add_argument("--report", type=Path)

    sources_parser = subparsers.add_parser("check-sources", help="检查资料可读性、转换状态和关键文件类型")
    sources_parser.add_argument("source_readiness_file", type=Path)
    sources_parser.add_argument("--report", type=Path)

    scoring_parser = subparsers.add_parser("check-scoring-applicability", help="检查评分标准适用标包范围")
    scoring_parser.add_argument("scoring_applicability_file", type=Path)
    scoring_parser.add_argument("--package", required=True)
    scoring_parser.add_argument("--report", type=Path)

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
        report = validate_chapter_plan(load_json(args.chapter_plan_file), load_json(args.requirements), scoring_map_data)
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
        report = validate_scoring_applicability(load_json(args.scoring_applicability_file), args.package)
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
