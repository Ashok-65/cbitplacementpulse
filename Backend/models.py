from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

class Alumni(db.Model):
    __tablename__ = 'alumni'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    graduation_year = db.Column(db.Integer, nullable=False)
    stream = db.Column(db.String(50), nullable=False)
    branch = db.Column(db.String(50), nullable=False, default='Other')
    company = db.Column(db.String(255))
    previous_company = db.Column(db.String(255))
    job_title = db.Column(db.String(255))
    previous_job_title = db.Column(db.String(255))
    salary = db.Column(db.Float)
    linkedin_url = db.Column(db.String(500))
    cbit_placement_url = db.Column(db.String(500))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    placement_status = db.Column(db.String(50), default='Placed')
    job_shifts = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50))
    data_source = db.Column(db.String(100), default='CBIT / LinkedIn')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    offers = db.relationship('PlacementOffer', back_populates='alumni', cascade='all, delete-orphan', lazy='selectin')
    
    def to_dict(self):
        companies = sorted({offer.company for offer in self.offers if offer.company})
        return {
            'id': self.id,
            'name': f'{self.first_name} {self.last_name}',
            'first_name': self.first_name,
            'last_name': self.last_name,
            'year': self.graduation_year,
            'passed_out_year': self.graduation_year,
            'stream': self.stream,
            'branch': self.branch or self.stream,
            'company': self.company or (companies[0] if companies else None),
            'companies': companies or ([self.company] if self.company else []),
            'previous_company': self.previous_company,
            'job_title': self.job_title,
            'previous_job_title': self.previous_job_title,
            'salary': self.salary,
            'linkedin_url': self.linkedin_url,
            'cbit_placement_url': self.cbit_placement_url,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'placement_status': self.placement_status,
            'job_shifts': self.job_shifts or 0,
            'category': self.category,
            'data_source': self.data_source,
            'offers': [offer.to_dict() for offer in self.offers],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class PlacementOffer(db.Model):
    __tablename__ = 'placement_offers'
    __table_args__ = (UniqueConstraint('alumni_id', 'academic_year', 'company', 'job_title', name='uq_alumni_offer'),)

    id = db.Column(db.Integer, primary_key=True)
    alumni_id = db.Column(db.Integer, db.ForeignKey('alumni.id'), nullable=False, index=True)
    academic_year = db.Column(db.String(9), nullable=False)
    company = db.Column(db.String(255), nullable=False)
    job_title = db.Column(db.String(255))
    source_url = db.Column(db.String(500))
    data_source = db.Column(db.String(120), nullable=False)
    alumni = db.relationship('Alumni', back_populates='offers')

    def to_dict(self):
        return {
            'id': self.id,
            'academic_year': self.academic_year,
            'company': self.company,
            'job_title': self.job_title,
            'source_url': self.source_url,
            'data_source': self.data_source
        }


class PlacementYearSummary(db.Model):
    __tablename__ = 'placement_year_summaries'

    academic_year = db.Column(db.String(9), primary_key=True)
    student_count = db.Column(db.Integer, nullable=False)
    placed_count = db.Column(db.Integer, nullable=False)
    placement_rate = db.Column(db.Float, nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    retrieved_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ScrapeLog(db.Model):
    __tablename__ = 'scrape_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    total_records = db.Column(db.Integer)
    successful = db.Column(db.Integer)
    failed = db.Column(db.Integer)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='In Progress')
    error_message = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'total_records': self.total_records,
            'successful': self.successful,
            'failed': self.failed,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'error_message': self.error_message
        }