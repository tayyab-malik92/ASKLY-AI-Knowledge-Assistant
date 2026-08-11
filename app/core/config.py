import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./askly.db")
    CHROMA_DB_DIR: str = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    LLM_MODEL: str = "llama-3.3-70b-versatile"

settings = Settings()