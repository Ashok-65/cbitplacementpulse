import os
import tempfile
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if os.getenv('VERCEL') == '1':
    INSTANCE_DIR = Path(tempfile.gettempdir()) / 'placementpulse'
else:
    INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DATABASE_URL = f"sqlite:///{(INSTANCE_DIR / 'alumni.db').as_posix()}"


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}