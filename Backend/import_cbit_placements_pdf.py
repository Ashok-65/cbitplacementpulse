"""Build the CBIT placement-record archive from its official year-wise PDFs."""

import argparse
import json
import re
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader


SOURCE_PAGE = "https://www.cbit.ac.in/placement_post/year-wise-placements-2021/"
OUTPUT_PATH = Path(__file__).parent / "data" / "cbit_pdf_placements.json"

COHORTS = {
    "2015-16": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2015-16-NIRF-Placed-Students.pdf",
        "placed": 676,
        "columns": [(90, 155, "roll"), (155, 300, "name"), (300, 340, "branch"), (340, 415, "company"), (415, 475, "campus"), (475, 1000, "ctc")],
    },
    "2016-17": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2016-17-NIRF-Placed-Students.pdf",
        "placed": 718,
        "columns": [(95, 155, "roll"), (155, 305, "name"), (305, 375, "company"), (375, 435, "campus"), (435, 1000, "ctc")],
    },
    "2017-18": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2017-18-NIRF-Placed-Students.pdf",
        "placed": 610,
        "columns": [(80, 145, "roll"), (145, 175, "branch"), (175, 300, "name"), (300, 400, "company"), (400, 470, "campus"), (470, 1000, "ctc")],
    },
    "2018-19": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2018-19-NIRF-Placed-Students.pdf",
        "placed": 734,
        "columns": [(85, 150, "roll"), (150, 190, "branch"), (190, 315, "name"), (315, 395, "company"), (395, 465, "campus"), (465, 1000, "ctc")],
    },
    "2019-20": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2019-20-NIRFPlaced-Students.pdf",
        "placed": 754,
        "columns": [(115, 170, "roll"), (170, 200, "branch"), (200, 322, "name"), (322, 425, "company"), (425, 480, "campus"), (480, 1000, "ctc")],
    },
    "2020-21": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2020-21-NIRF-Placed-Students.pdf",
        "placed": 744,
        "columns": [(110, 175, "roll"), (175, 300, "name"), (300, 345, "branch"), (345, 430, "company"), (430, 490, "campus"), (490, 1000, "ctc")],
    },
    "2021-22": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2021-22-NIRF-Placed-Students.pdf",
        "placed": 722,
        "columns": [(100, 145, "roll"), (145, 280, "name"), (280, 310, "branch"), (310, 405, "company"), (405, 460, "campus"), (460, 1000, "ctc")],
    },
    "2022-23": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2022-23-NIRF-Placed-Students.pdf",
        "placed": 718,
        "columns": [(60, 115, "roll"), (115, 285, "name"), (285, 315, "branch"), (315, 405, "company"), (405, 465, "campus"), (465, 1000, "ctc")],
    },
    "2023-24": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2023-24-NIRF-Placed-Students.pdf",
        "placed": 720,
        "columns": [(60, 120, "roll"), (120, 300, "name"), (300, 340, "branch"), (340, 480, "company"), (480, 540, "campus"), (540, 1000, "ctc")],
    },
    "2024-25": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/04/2024-25-NIRF-Placed-Students.pdf",
        "placed": 779,
        "columns": [(65, 120, "roll"), (120, 243, "name"), (243, 340, "branch"), (340, 440, "company"), (440, 495, "campus"), (495, 1000, "ctc")],
    },
    "2025-26": {
        "url": "https://www.cbit.ac.in/wp-content/uploads/2026/09/2025-26-UG-Placed-Students-18.09.2026.pdf",
        "placed": 723,
        "columns": [(60, 120, "roll"), (120, 250, "name"), (250, 395, "branch"), (395, 480, "company"), (480, 535, "campus"), (535, 1000, "ctc")],
    },
}


def _download_pdf(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "PlacementPulse CBIT PDF archive"})
    with urllib.request.urlopen(request, timeout=45) as response, destination.open("wb") as output:
        output.write(response.read())


def _column_for(x, columns):
    return next((field for start, end, field in columns if start <= x < end), None)


def extract_pdf_records(pdf_path, academic_year):
    cohort = COHORTS[academic_year]
    records = []
    for page_number, page in enumerate(PdfReader(pdf_path).pages, start=1):
        chunks = []

        def capture_text(text, _cm, tm, _font, _font_size):
            cleaned = " ".join(text.split())
            if cleaned:
                chunks.append((float(tm[4]), float(tm[5]), cleaned))

        page.extract_text(visitor_text=capture_text)
        anchors = []
        for x, y, text in chunks:
            digits = re.sub(r"\D", "", text)
            if _column_for(x, cohort["columns"]) == "roll" and 10 <= len(digits) <= 14:
                anchors.append({"x": x, "y": y, "roll": text})
        anchors.sort(key=lambda anchor: anchor["y"], reverse=True)

        if not anchors:
            continue

        row_chunks = defaultdict(lambda: defaultdict(list))
        for x, y, text in chunks:
            field = _column_for(x, cohort["columns"])
            if not field or field == "roll":
                continue
            nearest_index = min(range(len(anchors)), key=lambda index: abs(anchors[index]["y"] - y))
            anchor = anchors[nearest_index]
            previous_gap = abs(anchor["y"] - anchors[nearest_index - 1]["y"]) if nearest_index else None
            next_gap = abs(anchors[nearest_index + 1]["y"] - anchor["y"]) if nearest_index + 1 < len(anchors) else None
            band = min(6.0, (previous_gap / 2 - 0.1) if previous_gap else 6.0, (next_gap / 2 - 0.1) if next_gap else 6.0)
            if abs(anchor["y"] - y) <= band:
                row_chunks[nearest_index][field].append((y, x, text))

        for index, anchor in enumerate(anchors):
            fields = {}
            for field, values in row_chunks[index].items():
                ordered = [value[2] for value in sorted(values, key=lambda value: (-value[0], value[1]))]
                fields[field] = " ".join(ordered).strip()
            serial_candidates = [
                text for x, y, text in chunks
                if x < anchor["x"] and abs(y - anchor["y"]) <= 3.5 and re.fullmatch(r"\d{1,4}", text)
            ]
            ctc_match = re.search(r"\d+(?:\.\d+)?", fields.get("ctc", ""))
            digits = re.sub(r"\D", "", anchor["roll"])
            records.append({
                "academic_year": academic_year,
                "serial_number": int(serial_candidates[0]) if serial_candidates else None,
                "roll_number": digits,
                "student_name": fields.get("name", ""),
                "branch": fields.get("branch") or None,
                "company": fields.get("company", ""),
                "campus_status": fields.get("campus", ""),
                "package_lpa": float(ctc_match.group()) if ctc_match else None,
                "source_url": cohort["url"],
                "source_page": SOURCE_PAGE,
                "source_document": "CBIT official year-wise placement PDF",
                "pdf_page": page_number,
            })
    return records


def build_archive(input_dir=None):
    all_records = []
    count_summary = {}
    with tempfile.TemporaryDirectory(prefix="cbit-placement-pdfs-") as temporary_dir:
        for academic_year, cohort in COHORTS.items():
            pdf_path = None
            if input_dir:
                possible_names = (
                    f"{academic_year}.pdf",
                    Path(cohort["url"]).name,
                )
                pdf_path = next((input_dir / name for name in possible_names if (input_dir / name).is_file()), None)
                if pdf_path is None:
                    raise FileNotFoundError(f"No local PDF found for {academic_year} in {input_dir}")
            else:
                pdf_path = Path(temporary_dir) / f"{academic_year}.pdf"
                _download_pdf(cohort["url"], pdf_path)

            cohort_records = extract_pdf_records(pdf_path, academic_year)
            if len(cohort_records) != cohort["placed"]:
                raise ValueError(
                    f"{academic_year}: extracted {len(cohort_records)} rows, expected {cohort['placed']}"
                )
            if any(not record["roll_number"] for record in cohort_records):
                raise ValueError(f"{academic_year}: at least one extracted row has no roll number")
            serial_numbers = [record["serial_number"] for record in cohort_records]
            if set(serial_numbers) != set(range(1, cohort["placed"] + 1)):
                raise ValueError(f"{academic_year}: extracted serial numbers do not cover the official 1–{cohort['placed']} range")

            count_summary[academic_year] = {
                "count": len(cohort_records),
                "missing_names": sum(not record["student_name"] for record in cohort_records),
                "missing_companies": sum(not record["company"] for record in cohort_records),
                "missing_ctc": sum(record["package_lpa"] is None for record in cohort_records),
            }
            all_records.extend(cohort_records)

    return {
        "source_page": SOURCE_PAGE,
        "generated_from": "CBIT official year-wise placement PDFs",
        "records": all_records,
        "cohorts": [
            {
                "academic_year": academic_year,
                "expected_placed": cohort["placed"],
                "extracted_records": count_summary[academic_year]["count"],
                "pdf_blank_names": count_summary[academic_year]["missing_names"],
                "pdf_blank_companies": count_summary[academic_year]["missing_companies"],
                "pdf_blank_ctc": count_summary[academic_year]["missing_ctc"],
                "source_url": cohort["url"],
            }
            for academic_year, cohort in COHORTS.items()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="Use downloaded PDFs from this directory instead of fetching them")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    archive = build_archive(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(archive['records']):,} verified PDF placement rows to {args.output}")
    for cohort in archive["cohorts"]:
        print(
            f"{cohort['academic_year']}: {cohort['extracted_records']:,} / {cohort['expected_placed']:,}; "
            f"PDF blanks — names {cohort['pdf_blank_names']}, companies {cohort['pdf_blank_companies']}, "
            f"CTC {cohort['pdf_blank_ctc']}"
        )


if __name__ == "__main__":
    main()
