from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine
from app.api.chat import router as chat_router

# 1. Initialize FastAPI App ONCE with all metadata
app = FastAPI(title="ASKLY: AI Knowledge Assistant", version="1.0.0")

# 2. Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Initialize SQLite tables on launch
Base.metadata.create_all(bind=engine)

# 4. Include Routers
app.include_router(chat_router)

@app.get("/")
def root():
    return {"status": "online", "app": "Askly"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)