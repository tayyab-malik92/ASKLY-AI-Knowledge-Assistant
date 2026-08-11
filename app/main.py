from fastapi import FastAPI
from app.db.database import Base, engine
from app.api.chat import router as chat_router

# Initialize SQLite tables on launch
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ASKLY: AI Knowledge Assistant", version="1.0.0")

app.include_router(chat_router)

@app.get("/")
def root():
    return {"status": "online", "app": "Askly"}