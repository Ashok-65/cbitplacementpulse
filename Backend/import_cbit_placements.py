import argparse
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

from app import app, db
from models import Alumni, PlacementOffer, PlacementYearSummary


PROJECT_DIR = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = PROJECT_DIR / 'Data' / 'Company Wise Placed Students Database - 2021-22 to 2025-26 - Reg.zip'
SOURCE_URL = 'https://cbit.ac.in/placement_post/year-wise-placements-2021/'
YEAR_SUMMARIES = {
    '2021-22': (884, 722, 82),
    '2022-23': (930, 718, 77),
    '2023-24': (954, 720, 76),
    '2024-25': (950, 779, 82),
    '2025-26': (877, 723, 82),
}
SOURCE_FILES = {'2023-24', '2024-25', '2025-26'}


def normalize_header(value):
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def normalize_branch(value):
    branch = re.sub(r'\s+', ' ', str(value or '').strip())
    lowered = branch.lower()
    if 'information technology' in lowered or lowered.startswith('it'):
        stream = 'IT'
    elif 'computer science' in lowered or lowered.startswith('cse'):
        stream = 'IT'
    elif 'artificial intelligence' in lowered or lowered.startswith('ai'):
        stream = 'AI & Data Science'
    elif 'electronics' in lowered or lowered.startswith('ece') or 'vlsi' in lowered:
        stream = 'ECE'
    elif 'electrical' in lowered or lowered.startswith('eee'):
        stream = 'EEE'
    elif 'mechanical' in lowered or lowered.startswith('mech') or 'production' in lowered:
        stream = 'Core Mechanical'
    elif 'civil' in lowered:
        stream = 'Civil'
    elif 'chemical' in lowered:
        stream = 'Chemical'
    elif 'biotech' in lowered or 'bio-tech' in lowered:
        stream = 'Biotechnology'
    elif 'mca' in lowered:
        stream = 'MCA'
    elif 'mba' in lowered:
        stream = 'MBA'
    else:
        stream = branch or 'Other'
    return branch[:50] or 'Other', stream[:50]


def read_source_students():
    students = {}
    if not ARCHIVE_PATH.is_file():
        raise FileNotFoundError(f'CBIT source archive not found: {ARCHIVE_PATH}')

    with ZipFile(ARCHIVE_PATH) as archive:
        for filename in archive.namelist():
            year_match = re.match(r'(202[3-5]-\d{2})', Path(filename).name)
            if not year_match or year_match.group(1) not in SOURCE_FILES:
                continue

            academic_year = year_match.group(1)
            graduation_year = int(academic_year[5:]) + 2000
            workbook = load_workbook(archive.open(filename), read_only=True, data_only=True)
            worksheet = workbook.worksheets[0]
            rows = worksheet.iter_rows(values_only=True)
            headers = [normalize_header(value) for value in next(rows, ())]
            indexes = {
                'roll': next((i for i, value in enumerate(headers) if value.startswith('rollno')), None),
                'name': next((i for i, value in enumerate(headers) if value in {'fullname', 'nameofthestudent'}), None),
                'branch': next((i for i, value in enumerate(headers) if 'specialization' in value), None),
                'company': next((i for i, value in enumerate(headers) if 'company' in value and 'offer' in value), None),
            }
            if any(index is None for index in indexes.values()):
                workbook.close()
                raise ValueError(f'Unsupported CBIT workbook columns: {filename}')

            for row in rows:
                name = str(row[indexes['name']] or '').strip()
                roll = str(row[indexes['roll']] or '').strip()
                company = re.sub(r'\s+', ' ', str(row[indexes['company']] or '').strip())
                branch, stream = normalize_branch(row[indexes['branch']])
                if not name or not roll or not company or company.lower() in {'na', 'n/a', 'none'}:
                    continue

                first_name, _, remaining_name = name.partition(' ')
                last_name = remaining_name.strip() or first_name
                key = (academic_year, roll)
                student = students.setdefault(key, {
                    'first_name': first_name,
                    'last_name': last_name,
                    'graduation_year': graduation_year,
                    'branch': branch,
                    'stream': stream,
                    'academic_year': academic_year,
                    'companies': set(),
                })
                student['companies'].add(company)

            workbook.close()

    return list(students.values())


def print_preview(students):
    by_year = defaultdict(lambda: {'students': 0, 'offers': 0})
    for student in students:
        summary = by_year[student['academic_year']]
        summary['students'] += 1
        summary['offers'] += len(student['companies'])
    print({
        'source_archive': ARCHIVE_PATH.name,
        'named_workbooks': dict(sorted(by_year.items())),
        'official_year_summaries': len(YEAR_SUMMARIES),
        'personal_contact_fields_imported': 0,
    })


def import_data(students):
    inserted_students = 0
    updated_students = 0
    inserted_offers = 0

    for student in students:
        alumni = Alumni.query.filter_by(
            first_name=student['first_name'],
            last_name=student['last_name'],
            graduation_year=student['graduation_year'],
            branch=student['branch'],
        ).first()
        if alumni is None:
            alumni = Alumni(
                first_name=student['first_name'],
                last_name=student['last_name'],
                graduation_year=student['graduation_year'],
                stream=student['stream'],
                branch=student['branch'],
                placement_status='Placed',
                cbit_placement_url=SOURCE_URL,
                data_source=f"CBIT placement workbook {student['academic_year']}",
            )
            db.session.add(alumni)
            db.session.flush()
            inserted_students += 1
        else:
            updated_students += 1
            alumni.stream = student['stream']
            alumni.placement_status = 'Placed'
            alumni.cbit_placement_url = SOURCE_URL
            alumni.data_source = f"CBIT placement workbook {student['academic_year']}"

        existing_offers = {
            (offer.academic_year, offer.company.casefold(), (offer.job_title or '').casefold())
            for offer in alumni.offers
        }
        for company in student['companies']:
            offer_key = (student['academic_year'], company.casefold(), '')
            if offer_key in existing_offers:
                continue
            db.session.add(PlacementOffer(
                alumni=alumni,
                academic_year=student['academic_year'],
                company=company,
                source_url=SOURCE_URL,
                data_source=f"CBIT placement workbook {student['academic_year']}",
            ))
            existing_offers.add(offer_key)
            inserted_offers += 1

    for academic_year, (student_count, placed_count, placement_rate) in YEAR_SUMMARIES.items():
        summary = db.session.get(PlacementYearSummary, academic_year)
        if summary is None:
            summary = PlacementYearSummary(academic_year=academic_year)
            db.session.add(summary)
        summary.student_count = student_count
        summary.placed_count = placed_count
        summary.placement_rate = placement_rate
        summary.source_url = SOURCE_URL
        summary.retrieved_at = datetime.now(timezone.utc)

    db.session.commit()
    return {
        'students_inserted': inserted_students,
        'students_updated': updated_students,
        'offers_inserted': inserted_offers,
        'official_year_summaries': len(YEAR_SUMMARIES),
    }


def main():
    parser = argparse.ArgumentParser(description='Import verified CBIT placement workbook data.')
    parser.add_argument('--dry-run', action='store_true', help='Inspect source counts without writing to the database.')
    arguments = parser.parse_args()
    students = read_source_students()
    print_preview(students)
    if arguments.dry_run:
        return
    with app.app_context():
        db.create_all()
        print(import_data(students))


if __name__ == '__main__':
    main()