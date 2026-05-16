#!/usr/bin/env python3
"""Build page-aware SSC stock comment data for the static UI."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "docs" / "pdfs"
OUT = ROOT / "data" / "processed"
WEB_ASSETS = ROOT / "docs" / "assets"

AREA_VALUES = {
    "AI",
    "AK Total",
    "BSAI",
    "BSAI/GOA",
    "Bogoslof",
    "BS",
    "BS/EAI",
    "C",
    "CAI",
    "CAI/WAI",
    "E",
    "EAI",
    "EAI/BS",
    "EBS",
    "EBS/EAI",
    "EYAK/SEO",
    "GOA Total",
    "SEO",
    "State GHL",
    "Subtotal",
    "Total",
    "W",
    "WAI",
    "W/C",
    "W/C/WYAK",
    "W/C (+ WYAK for 2024 and 2025 only)",
    "WYAK",
}


@dataclass(frozen=True)
class Stock:
    stock: str
    fmp: str
    aliases: tuple[str, ...]


STOCKS: tuple[Stock, ...] = (
    Stock("Walleye pollock", "BSAI/GOA", ("pollock", "walleye pollock", "EBS pollock", "AI pollock", "Bogoslof pollock", "GOA pollock")),
    Stock("Pacific cod", "BSAI/GOA", ("Pacific cod", "EBS Pacific cod", "AI Pacific cod", "GOA Pacific cod", "cod stock")),
    Stock("Sablefish", "BSAI/GOA", ("sablefish", "Alaska sablefish")),
    Stock("Yellowfin sole", "BSAI", ("yellowfin sole",)),
    Stock("Greenland turbot", "BSAI/GOA", ("Greenland turbot",)),
    Stock("Arrowtooth flounder", "BSAI/GOA", ("arrowtooth flounder",)),
    Stock("Kamchatka flounder", "BSAI/GOA", ("Kamchatka flounder",)),
    Stock("Northern rock sole", "BSAI/GOA", ("northern rock sole",)),
    Stock("Southern rock sole", "GOA", ("southern rock sole",)),
    Stock("Flathead sole", "BSAI/GOA", ("flathead sole",)),
    Stock("Alaska plaice", "BSAI", ("Alaska plaice",)),
    Stock("Other flatfish", "BSAI", ("other flatfish",)),
    Stock("Deepwater flatfish", "GOA", ("deepwater flatfish", "Dover sole", "deepsea sole")),
    Stock("Shallow-water flatfish", "GOA", ("shallow-water flatfish", "shallow water flatfish")),
    Stock("Rex sole", "GOA", ("rex sole",)),
    Stock("Pacific ocean perch", "BSAI/GOA", ("Pacific ocean perch", "POP")),
    Stock("Northern rockfish", "BSAI/GOA", ("northern rockfish",)),
    Stock("Dusky rockfish", "GOA", ("dusky rockfish",)),
    Stock("Rougheye/blackspotted rockfish", "BSAI/GOA", ("rougheye", "blackspotted", "RE/BS", "BS/RE")),
    Stock("Shortraker rockfish", "BSAI/GOA", ("shortraker rockfish",)),
    Stock("Other rockfish", "BSAI/GOA", ("other rockfish",)),
    Stock("Demersal shelf rockfish", "GOA", ("demersal shelf rockfish", "DSR", "yelloweye rockfish")),
    Stock("Thornyhead rockfish", "GOA", ("thornyhead", "thornyhead rockfish")),
    Stock("Atka mackerel", "BSAI/GOA", ("Atka mackerel",)),
    Stock("Skates", "BSAI/GOA", ("skate", "skates", "Alaska skate", "big skate", "longnose skate")),
    Stock("Sharks", "BSAI/GOA", ("shark", "sharks")),
    Stock("Octopuses", "BSAI", ("octopus", "octopuses")),
    Stock("Squids", "BSAI/GOA", ("squid", "squids")),
    Stock("Forage fish", "BSAI/GOA", ("forage fish", "forage species")),
    Stock("Grenadiers", "BSAI/GOA", ("grenadier", "grenadiers")),
    Stock("EBS snow crab", "BSAI", ("snow crab", "EBS snow crab")),
    Stock("Bristol Bay red king crab", "BSAI", ("Bristol Bay red king crab", "BB red king crab")),
    Stock("EBS Tanner crab", "BSAI", ("Tanner crab", "EBS Tanner crab")),
    Stock("Pribilof Islands red king crab", "BSAI", ("Pribilof Islands red king crab",)),
    Stock("Pribilof Islands blue king crab", "BSAI", ("Pribilof Islands blue king crab",)),
    Stock("St. Matthew Island blue king crab", "BSAI", ("St. Matthew", "St Matthew", "blue king crab")),
    Stock("Norton Sound red king crab", "BSAI", ("Norton Sound red king crab", "NSRKC")),
    Stock("Aleutian Islands golden king crab", "BSAI", ("golden king crab", "AI golden king crab")),
    Stock("Western Aleutian Islands red king crab", "BSAI", ("Western AI red king crab", "Western Aleutian Islands red king crab")),
    Stock("Scallops", "BSAI/GOA", ("scallop", "scallops")),
    Stock("Salmon", "BSAI/GOA", ("salmon", "chum salmon", "Chinook salmon", "pink salmon", "sockeye salmon")),
    Stock("Halibut", "BSAI/GOA", ("halibut",)),
    Stock("Herring", "BSAI/GOA", ("herring", "Togiak herring")),
)


ACTION_PATTERNS = {
    "request": re.compile(r"\bSSC\s+(requests?|asked|recommended that)\b", re.I),
    "recommendation": re.compile(r"\bSSC\s+(recommends?|recommended)\b", re.I),
    "support/concur": re.compile(r"\bSSC\s+(supports?|supported|concurs?|concurred|agrees?|agreed|endorses?)\b", re.I),
    "concern": re.compile(r"\bSSC\s+(is concerned|expressed concern|notes? .*concern|highlights?)\b", re.I),
    "appreciation": re.compile(r"\bSSC\s+(thanks?|appreciates?|commended|commends?)\b", re.I),
    "note": re.compile(r"\bSSC\s+(notes?|recognizes?|acknowledges?|reiterates?|suggests?|encourages?)\b", re.I),
}


def normalize_ws(text: str) -> str:
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.match(r"^\d+\s+of\s+\d+\b", stripped):
            continue
        if re.match(r"^SSC Report.*(?:Council|Draft)", stripped, re.I):
            continue
        if re.match(r"^(December|October|June|September)\s+\d{4}$", stripped):
            continue
        lines.append(line.rstrip())
    return lines


def extract_pages(pdf: Path) -> list[str]:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
    pages = proc.stdout.split("\f")
    return [page for page in pages if page.strip()]


def report_pages(pdf: Path) -> tuple[list[str], list[dict[str, str | int]]]:
    pages = extract_pages(pdf)
    return pages, paragraphs_by_page(pages)


def paragraphs_by_page(pages: list[str]) -> list[dict[str, str | int]]:
    blocks: list[dict[str, str | int]] = []
    for page_number, page in enumerate(pages, start=1):
        current: list[str] = []
        for line in clean_lines(page):
            if line.strip():
                current.append(line)
            elif current:
                text = normalize_ws("\n".join(current))
                if len(text) > 20:
                    blocks.append({"page": page_number, "text": text})
                current = []
        if current:
            text = normalize_ws("\n".join(current))
            if len(text) > 20:
                blocks.append({"page": page_number, "text": text})
    return blocks


def report_date(name: str, text: str) -> tuple[str, str]:
    year_match = re.search(r"(20\d{2}|19\d{2})", name) or re.search(r"\b(20\d{2}|19\d{2})\b", text[:2000])
    month_match = re.search(r"\b(Dec|December|Oct|October|June|Sept|September)\b", name, re.I)
    if not month_match:
        month_match = re.search(r"\b(December|October|June|September|February|April)\b", text[:2000], re.I)
    return (year_match.group(1) if year_match else "", month_match.group(1) if month_match else "")


def update_context(para: str, current: str) -> str:
    if re.search(r"\bBSAI\b.*\bGOA\b|\bGOA\b.*\bBSAI\b", para):
        return "BSAI/GOA"
    if re.search(r"\b(BSAI|Bering Sea|Aleutian Islands|EBS)\b", para):
        return "BSAI"
    if re.search(r"\b(GOA|Gulf of Alaska)\b", para):
        return "GOA"
    return current


def infer_fmp(stock: Stock, para: str, context_fmp: str) -> str:
    if stock.fmp != "BSAI/GOA":
        return stock.fmp
    has_bsai = bool(re.search(r"\b(BSAI|Bering Sea|Aleutian Islands|EBS|AI)\b", para))
    has_goa = bool(re.search(r"\b(GOA|Gulf of Alaska)\b", para))
    if has_bsai and has_goa:
        return "BSAI/GOA"
    if has_bsai:
        return "BSAI"
    if has_goa:
        return "GOA"
    if context_fmp:
        return context_fmp
    if re.search(r"\b(bogoslof|ebs)\b", para, re.I):
        return "BSAI"
    return stock.fmp


def section_label(para: str, previous: str) -> str:
    if len(para) <= 140 and (
        re.match(r"^[A-Z]\d+\b", para)
        or re.search(r"\b(SAFE|Specifications|Groundfish|Crab|Ecosystem Status|Rockfish|Flatfish)\b", para)
    ):
        return para
    return previous


def stock_matches(para: str) -> list[tuple[Stock, str]]:
    matches: list[tuple[Stock, str]] = []
    for stock in STOCKS:
        found: list[str] = []
        for alias in stock.aliases:
            flags = 0 if alias.isupper() else re.I
            if re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", para, flags):
                found.append(alias)
        if found:
            matches.append((stock, "; ".join(sorted(set(found), key=str.lower))))
    return matches


def comment_type(para: str) -> str:
    for name, pattern in ACTION_PATTERNS.items():
        if pattern.search(para):
            return name
    if "SSC" in para:
        return "ssc_comment"
    return "context"


def make_excerpt(para: str, max_len: int = 520) -> str:
    if len(para) <= max_len:
        return para
    return para[:max_len].rsplit(" ", 1)[0] + "..."


def table_target_years(text: str, report_year: str) -> list[str]:
    years = re.findall(r"\b(20\d{2})\b", text)
    years = [year for year in years if year != report_year]
    if len(years) >= 2:
        return years[-2:]
    if len(years) == 1:
        return years
    if report_year:
        return [str(int(report_year) + 1), str(int(report_year) + 2)]
    return []


def table_fmp(text: str) -> str:
    if re.search(r"Gulf of Alaska|GOA", text, re.I):
        return "GOA"
    if re.search(r"Bering Sea|Aleutian|BSAI|crab", text, re.I):
        return "BSAI"
    return ""


def split_columns(line: str) -> list[str]:
    line = line.replace("−", "-").strip()
    line = re.sub(r"(?<=\d),(?=\s+\d{3}\b)", ",", line)
    line = re.sub(r"(?<=\d),\s+(?=\d{3}\b)", ",", line)
    return [part.strip() for part in re.split(r"\s{2,}", line) if part.strip()]


def is_numberish(value: str) -> bool:
    return bool(re.fullmatch(r"(?:n/a|-|[0-9][0-9,]*(?:\.[0-9]+)?)", value.strip(), re.I))


def clean_number(value: str) -> str:
    value = value.strip()
    if value.lower() == "n/a" or value == "-":
        return ""
    return value.replace(",", "")


def normalize_species_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" :")
    replacements = {
        "Pacific Cod": "Pacific cod",
        "Pacific Ocean perch": "Pacific ocean perch",
        "Deep-Water Flatfish": "Deep-water flatfish",
        "Shallow-Water Flatfish": "Shallow-water flatfish",
        "Arrowtooth Flounder": "Arrowtooth flounder",
        "Flathead Sole": "Flathead sole",
        "Rex Sole": "Rex sole",
        "Northern Rockfish": "Northern rockfish",
        "Shortraker Rockfish": "Shortraker rockfish",
        "Dusky Rockfish": "Dusky rockfish",
        "Thornyhead Rockfish": "Thornyhead rockfish",
        "Other Rockfish": "Other rockfish",
        "Atka mackerel": "Atka mackerel",
        "Blackspotted/Rougheye": "Blackspotted/Rougheye rockfish",
        "Blackspotted/Rougheye Rockfish": "Blackspotted/Rougheye rockfish",
        "Rougheye and Blackspotted Rockfish": "Rougheye and Blackspotted rockfish",
    }
    return replacements.get(value, value)


def parse_specification_rows(pdf: Path, pages: list[str], report_year: str) -> list[dict[str, str | int]]:
    records: list[dict[str, str | int]] = []
    active = False
    saw_header = False
    context = ""
    fmp = ""
    target_years: list[str] = []
    current_species = ""
    pending_species = ""
    continuation_area = ""
    pdf_url = f"pdfs/{quote(pdf.name)}"

    for page_number, page in enumerate(pages, start=1):
        for raw_line in page.splitlines():
            line = normalize_ws(raw_line)
            if not line:
                continue
            if re.search(r"Table \d+.*SSC recommended.*OFL.*ABC", line, re.I):
                active = True
                saw_header = False
                context = line
                fmp = table_fmp(line)
                target_years = table_target_years(line, report_year)
                current_species = ""
                pending_species = ""
                continuation_area = ""
                continue
            if not active:
                continue
            if line.startswith("Sources:") or re.match(r"General Groundfish|C\d+\s+", line):
                active = False
                continue
            if re.search(r"\bSpecies\b.*\bArea\b.*\bOFL\b.*\bABC\b", line):
                saw_header = True
                continue
            if not saw_header:
                if target_years and "Species" in line and "Area" in line:
                    saw_header = True
                continue
            if re.match(r"^\d+\s+of\s+\d+\b", line) or "Bold text indicates" in line:
                continue

            columns = split_columns(raw_line)
            if not columns:
                continue
            has_numbers = any(is_numberish(col) for col in columns)
            if not has_numbers:
                if re.search(r"[A-Za-z]", line) and not re.search(r"\b(OFL|ABC|Catch|TAC|Table|metric tons)\b", line):
                    if current_species and len(line) < 20 and ("/" in current_species or "Blackspotted" in current_species):
                        current_species = normalize_species_name(f"{current_species} {line}")
                    else:
                        pending_species = line if not pending_species else f"{pending_species} {line}"
                continue

            area_idx = None
            if len(columns) > 1 and columns[0] == "Total" and columns[1] in AREA_VALUES:
                continue
            for idx, col in enumerate(columns[:4]):
                if col in AREA_VALUES:
                    area_idx = idx
                    break
            if area_idx is None:
                if continuation_area and all(is_numberish(col) for col in columns):
                    area = continuation_area
                    species = current_species
                    values = columns
                else:
                    continue
            else:
                area = columns[area_idx]
                continuation_area = area if area.startswith("W/C") else ""
                if area_idx == 0:
                    species = pending_species or current_species
                else:
                    species = " ".join(columns[:area_idx])
                values = columns[area_idx + 1 :]
            species = normalize_species_name(species)
            if not species or species.lower() in {"total", "subtotal"}:
                continue
            current_species = species
            pending_species = ""
            values = [value for value in values if is_numberish(value)]
            if len(values) < 2 or not target_years:
                continue
            needed = 2 * len(target_years)
            rec_values = values[-needed:]
            if len(rec_values) < needed:
                continue
            for year, ofl, abc in zip(target_years, rec_values[0::2], rec_values[1::2]):
                records.append(
                    {
                        "stock": species,
                        "fmp": fmp,
                        "area": area,
                        "recommendation_year": year,
                        "report_year": report_year,
                        "source_file": pdf.name,
                        "page": page_number,
                        "ofl": clean_number(ofl),
                        "abc": clean_number(abc),
                        "units": "metric tons",
                        "table": context,
                        "page_url": f"{pdf_url}#page={page_number}",
                    }
                )
    return records


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WEB_ASSETS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | int]] = []
    specs: list[dict[str, str | int]] = []
    seen: set[tuple[str, str, str, int, str]] = set()

    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        pages, page_blocks = report_pages(pdf)
        whole_text = "\n".join(pages)
        year, month = report_date(pdf.stem, whole_text)
        specs.extend(parse_specification_rows(pdf, pages, year))
        context = ""
        section = ""
        pdf_url = f"pdfs/{quote(pdf.name)}"
        for idx, block in enumerate(page_blocks, start=1):
            para = str(block["text"])
            page = int(block["page"])
            context = update_context(para, context)
            section = section_label(para, section)
            matches = stock_matches(para)
            if not matches:
                continue
            ctype = comment_type(para)
            if ctype == "context" and "SSC" not in para and not re.search(r"\b(assessment|SAFE|OFL|ABC|model|risk table|harvest)\b", para, re.I):
                continue
            for stock, aliases in matches:
                fmp = infer_fmp(stock, para, context)
                key = (pdf.name, stock.stock, fmp, page, para[:180])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": len(rows) + 1,
                        "stock": stock.stock,
                        "fmp": fmp,
                        "comment_type": ctype,
                        "year": year,
                        "month": month,
                        "source_file": pdf.name,
                        "page": page,
                        "paragraph_index": idx,
                        "section": section,
                        "matched_terms": aliases,
                        "excerpt": make_excerpt(para),
                        "full_text": para,
                        "pdf_url": pdf_url,
                        "page_url": f"{pdf_url}#page={page}",
                    }
                )

    fieldnames = [
        "id",
        "stock",
        "fmp",
        "comment_type",
        "year",
        "month",
        "source_file",
        "page",
        "paragraph_index",
        "section",
        "matched_terms",
        "excerpt",
        "full_text",
        "pdf_url",
        "page_url",
    ]
    with (OUT / "ssc_stock_comments.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "records": rows,
        "filters": {
            "stocks": sorted({str(r["stock"]) for r in rows}),
            "years": sorted({str(r["year"]) for r in rows if r["year"]}),
            "fmps": ["BSAI", "GOA", "BSAI/GOA"],
            "comment_types": sorted({str(r["comment_type"]) for r in rows}),
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    (WEB_ASSETS / "comments.json").write_text(payload_json, encoding="utf-8")
    (WEB_ASSETS / "comments-data.js").write_text(
        f"window.SSC_COMMENTS_DATA = {payload_json};\n",
        encoding="utf-8",
    )

    counts = Counter((str(r["stock"]), str(r["fmp"])) for r in rows)
    years: dict[tuple[str, str], set[str]] = defaultdict(set)
    files: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_type: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = (str(row["stock"]), str(row["fmp"]))
        years[key].add(str(row["year"]))
        files[key].add(str(row["source_file"]))
        by_type[key][str(row["comment_type"])] += 1
    with (OUT / "ssc_stock_summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stock", "fmp", "records", "years", "source_files", "comment_types"])
        writer.writeheader()
        for (stock, fmp), count in sorted(counts.items()):
            writer.writerow(
                {
                    "stock": stock,
                    "fmp": fmp,
                    "records": count,
                    "years": ";".join(sorted(years[(stock, fmp)])),
                    "source_files": len(files[(stock, fmp)]),
                    "comment_types": json.dumps(by_type[(stock, fmp)], sort_keys=True),
                }
            )

    spec_fields = [
        "stock",
        "fmp",
        "area",
        "recommendation_year",
        "report_year",
        "source_file",
        "page",
        "ofl",
        "abc",
        "units",
        "table",
        "page_url",
    ]
    with (OUT / "ssc_abc_ofl_recommendations.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=spec_fields)
        writer.writeheader()
        writer.writerows(specs)

    spec_payload = {
        "records": specs,
        "filters": {
            "stocks": sorted({str(r["stock"]) for r in specs}),
            "years": sorted({str(r["recommendation_year"]) for r in specs if r["recommendation_year"]}),
            "fmps": sorted({str(r["fmp"]) for r in specs if r["fmp"]}),
        },
    }
    (WEB_ASSETS / "specifications.json").write_text(json.dumps(spec_payload, ensure_ascii=False), encoding="utf-8")
    (WEB_ASSETS / "specifications-data.js").write_text(
        f"window.SSC_SPECIFICATIONS_DATA = {json.dumps(spec_payload, ensure_ascii=False)};\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} comment records and {len(specs)} OFL/ABC records from {len(list(PDF_DIR.glob('*.pdf')))} PDFs.")


if __name__ == "__main__":
    main()
