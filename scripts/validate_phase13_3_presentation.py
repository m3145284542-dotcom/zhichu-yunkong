"""Fail-closed package and render validation for the Phase 13.3 deck."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


EXPECTED_TITLES = [
    "让负荷预测服务于",
    "更低的预测 RMSE，并未带来更低的储能决策 regret",
    "预测只是中间环节，调度结果才是工程终点",
    "模型不只要预测得准，还要在 Validation 上支持更好的储能决策",
    "DOEF 在 Validation 上按决策 regret 冻结权重，再进入 Test",
    "DOEF 同时降低预测误差与储能决策 regret",
    "RMSE 衡量预测误差；regret 衡量误差经过调度后的工程后果",
    "全部八栋固定建筑均被展示：六胜、两平、零负",
    "权重在 Validation 冻结，Test 不参与选择",
    "冻结流程明确了次日预测如何生成储能调度，但尚非现场部署",
    "创新不在基础预测器，而在把模型选择对齐储能决策",
    "让预测评价",
    "建筑范围在结果评估前冻结",
    "因果特征与时间切分共同约束信息边界",
    "基础模型是对照与组件，不是被包装的创新点",
    "同一冻结电池约束保证方法间可比",
    "完整预测指标用于核查，不替代下游决策评价",
    "决策指标必须连同范围与聚合口径一起解释",
    "冻结调度轨迹只用于说明流程，不代表普遍表现",
    "逐建筑权重来自预先声明的 Validation 搜索",
    "冻结 bootstrap 支持固定八栋建筑范围内的差异",
    "报告公式与冻结预测逐值一致",
    "负结果被保留，但不用于 Test 后反向改选算法",
]

REQUIRED_TEXT = {
    1: ["全球人工智能算法精英大赛 · AI+能源主题赛"],
    3: ["Prediction is an input to the decision — not the endpoint"],
    6: ["6.36%", "3.61%", "6  /  2  /  0"],
    8: ["8 / 8", "六胜、两平、零负"],
    9: ["NO TEST-TIME TUNING", "evaluation only"],
    19: ["the case and values remain frozen"],
    21: ["−0.004198", "−0.006850", "−0.001719"],
    22: ["5,760", "0.0 kW"],
    23: ["20.4635 kW", "11.1274 kW", "NEGATIVE RESULT RETAINED"],
}

FORBIDDEN_TEXT = [
    "工作标题 · 正式赛题名称待核验",
    "全面提高预测精度",
    "所有场景下均优于",
    "显著提升",
    "证明了",
    "真实部署",
    "商业收益",
    "现场控制实验",
    "重新优化",
]

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def rel_source(rel_path: str) -> str:
    if rel_path == "_rels/.rels":
        return ""
    directory, name = posixpath.split(rel_path)
    parent = posixpath.dirname(directory)
    return posixpath.join(parent, name.removesuffix(".rels"))


def slide_number(name: str) -> int:
    return int(re.search(r"slide(\d+)\.xml$", name).group(1))


def rendered_count(directory: Path) -> int:
    if not directory.exists():
        return 0
    return len([p for p in directory.glob("slide-*.png") if p.is_file()])


def layout_out_of_bounds(directory: Path) -> list[dict]:
    issues: list[dict] = []
    for layout_path in sorted(directory.glob("slide-*.layout.json")):
        data = json.loads(layout_path.read_text(encoding="utf-8"))
        frame = data["slide"]["frame"]
        width, height = float(frame["width"]), float(frame["height"])

        def walk(value):
            if isinstance(value, dict):
                bbox = value.get("bbox")
                if isinstance(bbox, list) and len(bbox) == 4:
                    left, top, box_width, box_height = map(float, bbox)
                    if left < -1 or top < -1 or left + box_width > width + 1 or top + box_height > height + 1:
                        issues.append({"file": layout_path.name, "id": value.get("aid") or value.get("id"), "bbox": bbox})
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(data.get("elements", []))
        walk(data.get("inheritedLayers", []))
    return issues


def validate(args) -> dict:
    pptx = args.pptx.resolve()
    result = {
        "phase": "13.3",
        "pptx": pptx.as_posix(),
        "status": "BLOCKED",
        "checks": {},
        "errors": [],
    }
    with zipfile.ZipFile(pptx) as archive:
        names = set(archive.namelist())
        bad_crc = archive.testzip()
        result["checks"]["zip_crc"] = "PASS" if bad_crc is None else "FAIL"
        if bad_crc:
            result["errors"].append(f"CRC failure: {bad_crc}")

        xml_names = sorted(name for name in names if name.endswith((".xml", ".rels")))
        roots = {}
        for name in xml_names:
            try:
                roots[name] = ET.fromstring(archive.read(name))
            except ET.ParseError as exc:
                result["errors"].append(f"XML parse failure {name}: {exc}")
        result["checks"]["xml_parts_parsed"] = len(roots)

        slide_names = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=slide_number,
        )
        notes = [name for name in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)]
        media = [name for name in names if name.startswith("ppt/media/") and not name.endswith("/")]
        result["checks"].update({"slides": len(slide_names), "notes": len(notes), "media": len(media)})
        if len(slide_names) != 23 or len(notes) != 23 or not media:
            result["errors"].append("Expected 23 slides, 23 notes slides, and embedded media")

        external = []
        missing_targets = []
        for name, root in roots.items():
            if not name.endswith(".rels"):
                continue
            source = rel_source(name)
            base = posixpath.dirname(source)
            for rel in root:
                target = rel.attrib.get("Target", "")
                if rel.attrib.get("TargetMode") == "External":
                    external.append({"part": name, "target": target})
                elif target and not target.startswith("#"):
                    resolved = posixpath.normpath(posixpath.join(base, target)).lstrip("/")
                    if resolved not in names:
                        missing_targets.append({"part": name, "target": target, "resolved": resolved})
        result["checks"]["external_relationships"] = len(external)
        result["checks"]["missing_relationship_targets"] = len(missing_targets)
        if external or missing_targets:
            result["errors"].append(f"Broken/external relationships: external={external}, missing={missing_targets}")

        presentation = roots.get("ppt/presentation.xml")
        size = presentation.find("p:sldSz", NS) if presentation is not None else None
        dimensions = [int(size.attrib["cx"]), int(size.attrib["cy"])] if size is not None else []
        result["checks"]["slide_size_emu"] = dimensions
        if dimensions != [12192000, 6858000]:
            result["errors"].append(f"Unexpected slide size: {dimensions}")

        all_text = []
        for index, name in enumerate(slide_names, start=1):
            root = roots[name]
            text = " | ".join((node.text or "") for node in root.findall(".//a:t", NS))
            all_text.append(text)
            expected_id = f"SB-{'M' if index <= 12 else 'A'}{index if index <= 12 else index - 12:02d}"
            if expected_id not in text or EXPECTED_TITLES[index - 1] not in text:
                result["errors"].append(f"Storyboard/title mismatch on slide {index}")
            for required in REQUIRED_TEXT.get(index, []):
                if required not in text:
                    result["errors"].append(f"Missing required text on slide {index}: {required}")
            for shape in root.findall(".//p:sp", NS):
                if shape.find(".//p:ph", NS) is not None:
                    placeholder_text = "".join((node.text or "") for node in shape.findall(".//a:t", NS)).strip()
                    if not placeholder_text:
                        result["errors"].append(f"Empty slide placeholder on slide {index}")
        joined = "\n".join(all_text)
        forbidden_hits = [item for item in FORBIDDEN_TEXT if item in joined]
        result["checks"]["forbidden_claim_hits"] = forbidden_hits
        if forbidden_hits:
            result["errors"].append(f"Forbidden/unresolved wording present: {forbidden_hits}")

        package_text = "\n".join(archive.read(name).decode("utf-8", errors="ignore") for name in xml_names)
        local_paths = re.findall(r"(?:file:/+|[A-Za-z]:\\)[^<\s\"]+", package_text)
        result["checks"]["local_path_references"] = local_paths
        if local_paths:
            result["errors"].append(f"Local path references present: {local_paths[:5]}")

        typefaces = sorted(set(re.findall(r'typeface="([^"]+)"', package_text)))
        result["checks"]["typefaces"] = typefaces
        blocked_fonts = sorted(set(typefaces) & {"Noto Sans CJK SC", "Aptos"})
        if blocked_fonts or "Microsoft YaHei" not in typefaces or "Arial" not in typefaces:
            result["errors"].append(f"Unsafe or missing presentation font declarations: {typefaces}")

        shadows = []
        for name, root in roots.items():
            for node in root.findall(".//a:outerShdw", NS):
                try:
                    values = {key: int(node.attrib[key]) for key in ("blurRad", "dist", "dir") if key in node.attrib}
                except ValueError:
                    result["errors"].append(f"Non-integer shadow value in {name}")
                    continue
                shadows.append({"part": name, **values})
                if any(value < 0 or value > 2_147_483_647 for value in values.values()) or values.get("dir", 0) > 21_600_000:
                    result["errors"].append(f"Invalid shadow in {name}: {values}")
        result["checks"]["valid_shadow_count"] = len(shadows)

    if args.pdf:
        pdf_bytes = args.pdf.read_bytes()
        pdf_pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
        result["checks"]["pdf_pages"] = pdf_pages
        if pdf_pages != 23:
            result["errors"].append(f"Expected 23 PDF pages, found {pdf_pages}")
    if args.render_dir:
        count = rendered_count(args.render_dir)
        result["checks"]["artifact_rendered_slides"] = count
        if count != 23:
            result["errors"].append(f"Expected 23 artifact-tool renders, found {count}")
        out_of_bounds = layout_out_of_bounds(args.render_dir)
        result["checks"]["out_of_bounds"] = out_of_bounds
        if out_of_bounds:
            result["errors"].append(f"Out-of-bounds layout elements: {out_of_bounds[:5]}")
    if args.lo_render_dir:
        count = rendered_count(args.lo_render_dir)
        result["checks"]["libreoffice_rendered_slides"] = count
        if count != 23:
            result["errors"].append(f"Expected 23 LibreOffice renders, found {count}")

    result["status"] = "PASS" if not result["errors"] else "BLOCKED"
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--lo-render-dir", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = validate(args)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
