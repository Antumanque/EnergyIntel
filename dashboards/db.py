import os
from functools import lru_cache
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_engine():
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")

    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/"
    return create_engine(url)
