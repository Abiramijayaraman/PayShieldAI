# src/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./payshield.db')
    OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')

settings = Settings()
