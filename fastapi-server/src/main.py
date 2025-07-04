from fastapi import FastAPI
from src.api import router

app = FastAPI(title="User Management API", version="1.0.0")

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)