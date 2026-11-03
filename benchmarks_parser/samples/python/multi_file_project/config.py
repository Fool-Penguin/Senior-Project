# Configuration module
import os
class AppConfig:
    DEBUG = os.getenv("APP_DEBUG", "False").lower() == "true"
    DB_URI = os.getenv("DB_URI", "sqlite:///app.db")
    MAX_PAYLOAD_SIZE = 1048576  # 1 MB
