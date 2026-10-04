import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from sqlalchemy import inspect, text
from models import db, Alumni, ScrapeLog, PlacementOffer, PlacementYearSummary
from config import config
from dotenv import load_dotenv
import csv
import json
from datetime import datetime
import io
import logging

load_dotenv()

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Frontend'))
CBIT_PDF_ARCHIVE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cbit_pdf_placements.json')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
environment = 'production' if os.getenv('VERCEL') == '1' else os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[environment])

db.init_app(app)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.after_request
def disable_dashboard_caching(response):
    if request.path.startswith('/api/') or request.path.endswith(('.html', '.js', '.css')):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

PLACEMENT_HIGHLIGHT_URL = 'https://www.cbit.ac.in/placement_post/placement-highlights/'
YEAR_WISE_PLACEMENT_URL = 'https://cbit.ac.in/placement_post/year-wise-placements-2021/'
FEATURED_PACKAGES = {
    '2021-22': {'company': 'Arcesium', 'ctc_lpa': 36.5},
    '2022-23': {'company': 'Electronic Arts', 'ctc_lpa': 44},
    '2023-24': {'company': 'Atlassian', 'ctc_lpa': 59.91},
    '2024-25': {'company': 'Microsoft', 'ctc_lpa': 51},
}


def seed_sample_data():
    if Alumni.query.filter_by(data_source='Demo sample').first() is not None:
        return

    sample_records = [
        {
            'first_name': 'Aarav', 'last_name': 'Sharma', 'graduation_year': 2022,
            'stream': 'IT', 'company': 'Microsoft', 'job_title': 'Software Engineer',
            'salary': 24.5, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Nisha', 'last_name': 'Patel', 'graduation_year': 2021,
            'stream': 'Core Mechanical', 'company': 'Tata Motors', 'job_title': 'Design Engineer',
            'salary': 18.2, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Karan', 'last_name': 'Iyer', 'graduation_year': 2023,
            'stream': 'IT', 'company': 'Google', 'job_title': 'Data Analyst',
            'salary': 26.8, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Meera', 'last_name': 'Rao', 'graduation_year': 2020,
            'stream': 'Core Mechanical', 'company': 'BHEL', 'job_title': 'Production Engineer',
            'salary': 15.4, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Rohan', 'last_name': 'Singh', 'graduation_year': 2024,
            'stream': 'IT', 'company': 'Amazon', 'job_title': 'Cloud Engineer',
            'salary': 28.7, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Sneha', 'last_name': 'Nair', 'graduation_year': 2022,
            'stream': 'IT', 'company': 'Infosys', 'job_title': 'Full Stack Developer',
            'salary': 22.1, 'placement_status': 'Higher Studies'
        },
        {
            'first_name': 'Vikram', 'last_name': 'Joshi', 'graduation_year': 2021,
            'stream': 'Core Mechanical', 'company': 'L&T', 'job_title': 'Project Engineer',
            'salary': 16.9, 'placement_status': 'Placed'
        },
        {
            'first_name': 'Priya', 'last_name': 'Menon', 'graduation_year': 2023,
            'stream': 'IT', 'company': 'Meta', 'job_title': 'Frontend Engineer',
            'salary': 30.2, 'placement_status': 'Placed'
        },
    ]

    for record in sample_records:
        alumni = Alumni(
            first_name=record['first_name'],
            last_name=record['last_name'],
            graduation_year=record['graduation_year'],
            stream=record['stream'],
            company=record['company'],
            job_title=record['job_title'],
            salary=record['salary'],
            placement_status=record['placement_status'],
            data_source='Demo sample'
        )
        db.session.add(alumni)

    db.session.commit()


def ensure_alumni_schema():
    with app.app_context():
        inspector = inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('alumni')}
        migration_columns = {
            'branch': 'VARCHAR(50) DEFAULT "Other"',
            'previous_company': 'VARCHAR(255)',
            'previous_job_title': 'VARCHAR(255)',
            'cbit_placement_url': 'VARCHAR(500)',
            'location': 'VARCHAR(200)',
            'job_shifts': 'INTEGER DEFAULT 0',
            'data_source': 'VARCHAR(100) DEFAULT "CBIT / LinkedIn"'
        }

        for column_name, column_spec in migration_columns.items():
            if column_name not in columns:
                db.session.execute(text(f'ALTER TABLE alumni ADD COLUMN {column_name} {column_spec}'))

        db.session.commit()


def mark_legacy_demo_records():
    demo_records = [
        ('Aarav', 'Sharma', 2022, 'Microsoft', 'Software Engineer', 24.5),
        ('Nisha', 'Patel', 2021, 'Tata Motors', 'Design Engineer', 18.2),
        ('Karan', 'Iyer', 2023, 'Google', 'Data Analyst', 26.8),
        ('Meera', 'Rao', 2020, 'BHEL', 'Production Engineer', 15.4),
        ('Rohan', 'Singh', 2024, 'Amazon', 'Cloud Engineer', 28.7),
        ('Sneha', 'Nair', 2022, 'Infosys', 'Full Stack Developer', 22.1),
        ('Vikram', 'Joshi', 2021, 'L&T', 'Project Engineer', 16.9),
        ('Priya', 'Menon', 2023, 'Meta', 'Frontend Engineer', 30.2),
    ]
    for first_name, last_name, year, company, job_title, salary in demo_records:
        Alumni.query.filter_by(
            first_name=first_name,
            last_name=last_name,
            graduation_year=year,
            branch='Other',
            company=company,
            job_title=job_title,
            salary=salary,
            data_source='CBIT / LinkedIn'
        ).update({'data_source': 'Demo sample'}, synchronize_session=False)
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_alumni_schema()
    mark_legacy_demo_records()


@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/dashboard')
@app.route('/dashboard.html')
def serve_dashboard():
    return send_from_directory(FRONTEND_DIR, 'index.html')


# ============ ROUTES ============

@app.route('/api/alumni', methods=['GET'])
def get_alumni():
    try:
        filters = {}
        name = request.args.get('name') or request.args.get('student_name')
        branch = request.args.get('branch') or request.args.get('stream')
        year = request.args.get('year') or request.args.get('passed_out_year')
        placement_year = request.args.get('placement_year')
        placement = request.args.get('placement') or request.args.get('status')
        paginated = 'page' in request.args or 'limit' in request.args
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('limit', 50)), 1), 100)

        if name:
            filters['name'] = name
        if branch:
            filters['branch'] = branch
        if year:
            filters['year'] = year
        if placement_year:
            filters['placement_year'] = placement_year
        if placement:
            filters['placement'] = placement

        query = Alumni.query.filter(Alumni.data_source != 'Demo sample')

        if 'name' in filters:
            name_terms = filters['name'].split()
            name_conditions = [
                (Alumni.first_name.ilike(f"%{filters['name']}%")) |
                (Alumni.last_name.ilike(f"%{filters['name']}%"))
            ]
            if len(name_terms) > 1:
                name_conditions.append(
                    Alumni.first_name.ilike(f"{name_terms[0]}%") &
                    Alumni.last_name.ilike(f"%{' '.join(name_terms[1:])}%")
                )
            name_conditions.extend([
                Alumni.company.ilike(f"%{filters['name']}%"),
                Alumni.job_title.ilike(f"%{filters['name']}%"),
                Alumni.branch.ilike(f"%{filters['name']}%"),
                Alumni.stream.ilike(f"%{filters['name']}%"),
                Alumni.offers.any(PlacementOffer.company.ilike(f"%{filters['name']}%")),
                Alumni.offers.any(PlacementOffer.academic_year.ilike(f"%{filters['name']}%"))
            ])
            query = query.filter(db.or_(*name_conditions))

        if 'branch' in filters:
            query = query.filter(
                (Alumni.branch == filters['branch']) |
                (Alumni.stream == filters['branch'])
            )

        if 'year' in filters:
            query = query.filter_by(graduation_year=int(filters['year']))
        if 'placement_year' in filters:
            query = query.filter(Alumni.offers.any(PlacementOffer.academic_year == filters['placement_year']))
        if 'placement' in filters:
            query = query.filter(Alumni.placement_status.ilike(filters['placement']))

        query = query.order_by(Alumni.graduation_year.desc(), Alumni.last_name.asc())
        if paginated:
            total = query.count()
            alumni = query.offset((page - 1) * per_page).limit(per_page).all()
            return jsonify({
                'items': [student.to_dict() for student in alumni],
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            })

        alumni = query.all()
        return jsonify([a.to_dict() for a in alumni])

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cbit-pdf-placements', methods=['GET'])
def get_cbit_pdf_placements():
    try:
        return send_file(CBIT_PDF_ARCHIVE_PATH, mimetype='application/json', conditional=True)
    except FileNotFoundError:
        logger.error("CBIT PDF placement archive is missing: %s", CBIT_PDF_ARCHIVE_PATH)
        return jsonify({
            'error': 'The CBIT PDF placement archive is missing. Run Backend/import_cbit_placements_pdf.py to build it.'
        }), 503
    except OSError as error:
        logger.error("Unable to read CBIT PDF placement archive: %s", error)
        return jsonify({'error': 'Unable to read the CBIT PDF placement archive.'}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        summaries = PlacementYearSummary.query.order_by(PlacementYearSummary.academic_year.asc()).all()
        latest = summaries[-1] if summaries else None
        year_values = [{
            'academic_year': summary.academic_year,
            'students': summary.student_count,
            'placed': summary.placed_count,
            'placement_rate': summary.placement_rate,
            'offer_count': PlacementOffer.query.filter_by(academic_year=summary.academic_year).count()
        } for summary in summaries]
        branch_counts = db.session.query(
            Alumni.branch, db.func.count(db.func.distinct(Alumni.id))
        ).filter(
            Alumni.data_source != 'Demo sample',
            Alumni.data_source.like('CBIT placement workbook%')
        ).group_by(Alumni.branch).order_by(Alumni.branch).all()
        alumni_records = Alumni.query.filter(
            Alumni.data_source.like('CBIT placement workbook%')
        ).count()
        offer_count = PlacementOffer.query.count()

        return jsonify({
            'total_students': latest.student_count if latest else 0,
            'placed': latest.placed_count if latest else 0,
            'higher_studies': None,
            'avg_salary': None,
            'placement_rate': latest.placement_rate if latest else 0,
            'latest_academic_year': latest.academic_year if latest else None,
            'alumni_records': alumni_records,
            'offer_count': offer_count,
            'yearly_data': year_values,
            'branch_labels': [row[0] or 'Other' for row in branch_counts],
            'branch_counts': [row[1] for row in branch_counts]
        })
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/top-companies', methods=['GET'])
def get_top_companies():
    try:
        offers = db.session.query(
            PlacementOffer.company,
            db.func.count(PlacementOffer.id).label('count')
        ).join(Alumni).filter(
            Alumni.data_source != 'Demo sample'
        ).group_by(PlacementOffer.company).all()
        counts = {company: count for company, count in offers}
        legacy = db.session.query(
            Alumni.company,
            db.func.count(Alumni.id).label('count')
        ).filter(
            Alumni.data_source != 'Demo sample',
            Alumni.company.isnot(None),
            ~Alumni.offers.any()
        ).group_by(Alumni.company).all()
        for company, count in legacy:
            counts[company] = counts.get(company, 0) + count
        return jsonify([
            {'name': company, 'count': count}
            for company, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
        ])
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/yearly-insights', methods=['GET'])
def get_yearly_insights():
    try:
        summaries = PlacementYearSummary.query.order_by(PlacementYearSummary.academic_year.asc()).all()
        results = []
        for summary in summaries:
            year_offer_count = PlacementOffer.query.filter_by(academic_year=summary.academic_year).count()
            recruiter_rows = db.session.query(
                PlacementOffer.company,
                db.func.count(PlacementOffer.id).label('offer_count')
            ).filter_by(
                academic_year=summary.academic_year
            ).group_by(
                PlacementOffer.company
            ).order_by(
                db.desc('offer_count'), PlacementOffer.company.asc()
            ).limit(3).all()

            results.append({
                'academic_year': summary.academic_year,
                'students': summary.student_count,
                'placed': summary.placed_count,
                'placement_rate': summary.placement_rate,
                'offer_count': year_offer_count,
                'top_recruiters': [{'name': name, 'offers': count} for name, count in recruiter_rows],
                'recruiter_source_url': YEAR_WISE_PLACEMENT_URL if recruiter_rows else None,
                'featured_package': FEATURED_PACKAGES.get(summary.academic_year),
                'package_source_url': PLACEMENT_HIGHLIGHT_URL if summary.academic_year in FEATURED_PACKAGES else None,
                'package_note': 'Featured CBIT highlight; not a verified cohort maximum.'
            })
        return jsonify({
            'years': results,
            'source_url': YEAR_WISE_PLACEMENT_URL,
            'package_source_url': PLACEMENT_HIGHLIGHT_URL
        })
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Only CSV files allowed'}), 400

        csv_text = file.stream.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            return jsonify({'error': 'The CSV file is empty or has no header row'}), 400

        aliases = {
            'firstname': 'first_name', 'givenname': 'first_name',
            'lastname': 'last_name', 'surname': 'last_name', 'familyname': 'last_name',
            'name': 'full_name', 'fullname': 'full_name', 'alumniname': 'full_name',
            'year': 'graduation_year', 'graduationyear': 'graduation_year',
            'passedoutyear': 'graduation_year', 'batch': 'graduation_year',
            'stream': 'stream', 'branch': 'branch', 'department': 'stream', 'major': 'stream',
            'company': 'company', 'currentcompany': 'company', 'employer': 'company',
            'jobtitle': 'job_title', 'currentrole': 'job_title', 'role': 'job_title', 'designation': 'job_title',
            'salary': 'salary', 'ctc': 'salary', 'package': 'salary', 'salarylakhs': 'salary',
            'linkedin': 'linkedin_url', 'linkedinurl': 'linkedin_url', 'linkedinprofile': 'linkedin_url',
            'cbitplacementurl': 'cbit_placement_url', 'placementsourcelink': 'cbit_placement_url',
            'sourcelink': 'cbit_placement_url', 'email': 'email', 'phone': 'phone',
            'location': 'location', 'placementstatus': 'placement_status', 'status': 'placement_status',
            'previouscompany': 'previous_company', 'previousjobtitle': 'previous_job_title',
            'jobshifts': 'job_shifts', 'category': 'category', 'datasource': 'data_source'
        }
        header_map = {
            header: aliases.get(''.join(char for char in header.lower() if char.isalnum()))
            for header in reader.fieldnames
        }
        supported_headers = {value for value in header_map.values() if value}
        if not ({'full_name', 'first_name'} & supported_headers) or 'graduation_year' not in supported_headers:
            return jsonify({
                'error': 'CSV needs a name column (Name or First Name) and a graduation year column (Year or Graduation Year).'
            }), 400

        imported = 0
        updated = 0
        skipped = 0
        row_errors = []
        fields = (
            'stream', 'branch', 'company', 'job_title', 'salary', 'linkedin_url',
            'cbit_placement_url', 'email', 'phone', 'location', 'placement_status',
            'previous_company', 'previous_job_title', 'job_shifts', 'category', 'data_source'
        )

        for row_number, row in enumerate(reader, start=2):
            values = {
                header_map[header]: (value or '').strip()
                for header, value in row.items()
                if header in header_map and header_map[header]
            }
            first_name = values.get('first_name', '')
            last_name = values.get('last_name', '')
            if not first_name or not last_name:
                full_name = values.get('full_name', '').split()
                if len(full_name) >= 2:
                    first_name = first_name or full_name[0]
                    last_name = last_name or ' '.join(full_name[1:])

            try:
                graduation_year = int(float(values.get('graduation_year', '')))
                if graduation_year < 1900 or graduation_year > 2100:
                    raise ValueError
                if not first_name or not last_name:
                    raise ValueError('A first and last name are required')
                salary_value = values.get('salary')
                salary = float(salary_value.replace(',', '').replace('₹', '').rstrip('lL')) if salary_value else None
                shifts_value = values.get('job_shifts')
                job_shifts = int(shifts_value) if shifts_value else None
            except ValueError as error:
                skipped += 1
                if len(row_errors) < 20:
                    message = str(error) if str(error) else 'Invalid graduation year or numeric value'
                    row_errors.append({'row': row_number, 'error': message})
                continue

            existing = Alumni.query.filter_by(
                first_name=first_name,
                last_name=last_name,
                graduation_year=graduation_year
            ).first()
            alumni = existing or Alumni(
                first_name=first_name,
                last_name=last_name,
                graduation_year=graduation_year,
                stream=values.get('stream') or values.get('branch') or 'Other',
                branch=values.get('branch') or values.get('stream') or 'Other',
                placement_status=values.get('placement_status') or 'Pending'
            )
            for field in fields:
                value = values.get(field)
                if field == 'salary':
                    value = salary
                elif field == 'job_shifts':
                    value = job_shifts
                if value not in (None, ''):
                    setattr(alumni, field, value)
            if existing:
                updated += 1
            else:
                db.session.add(alumni)
                imported += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'CSV import completed',
            'total_rows': imported + updated + skipped,
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'row_errors': row_errors
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/import-template', methods=['GET'])
def import_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'First Name', 'Last Name', 'Graduation Year', 'Branch', 'Company', 'Job Title',
        'Salary', 'Placement Status', 'LinkedIn URL', 'CBIT Placement URL', 'Location',
        'Email', 'Phone', 'Previous Company', 'Previous Job Title'
    ])
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='alumni_import_template.csv'
    )


@app.route('/api/scrape', methods=['POST'])
def start_scraping():
    return jsonify({
        'error': 'Automatic LinkedIn scraping is not supported. Import verified placement records through CSV instead.'
    }), 410


@app.route('/api/export', methods=['GET'])
def export_data():
    try:
        format_type = request.args.get('format', 'csv').lower()
        
        alumni = Alumni.query.filter(Alumni.data_source != 'Demo sample').all()
        alumni_data = [a.to_dict() for a in alumni]
        
        if format_type == 'csv':
            output = io.StringIO()
            if alumni_data:
                writer = csv.DictWriter(output, fieldnames=alumni_data[0].keys())
                writer.writeheader()
                writer.writerows(alumni_data)
            
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'alumni_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
        
        elif format_type == 'json':
            return jsonify(alumni_data)
        
        else:
            return jsonify({'error': 'Unsupported format'}), 400
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['POST'])
def save_settings():
    try:
        data = request.get_json()
        
        return jsonify({
            'success': True,
            'message': 'Settings saved successfully'
        })
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/insights', methods=['GET'])
def get_insights():
    try:
        total = Alumni.query.count()
        
        return jsonify([
            {
                'title': 'IT Stream Performance',
                'description': f'IT Stream has the highest placement rate'
            },
            {
                'title': 'Core Mechanical Salary',
                'description': f'Core Mechanical stream salary is increasing'
            },
            {
                'title': 'Higher Education',
                'description': f'Students pursuing further studies'
            },
            {
                'title': 'Tech Companies',
                'description': f'Tech companies dominate with high placements'
            }
        ])
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify([])


@app.route('/api/seed', methods=['POST'])
def seed_demo_data():
    try:
        seed_sample_data()
        return jsonify({
            'success': True,
            'message': 'Sample alumni data loaded successfully.'
        })
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/<path:filename>')
def serve_static(filename):
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({'error': 'File not found'}), 404


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)