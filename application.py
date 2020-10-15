import os

from app import create_app


application = create_app(os.getenv("DM_ENVIRONMENT") or "development")
