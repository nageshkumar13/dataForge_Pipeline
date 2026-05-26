import os


os.environ.setdefault('DATABASE_URL', 'sqlite:///dataforge-test.db')
os.environ.setdefault('PIPELINE_SCAN_INTERVAL', '1')
