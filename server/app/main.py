from fastapi import FastAPI
from app.routes.urls import router as urls_router
from app.routes.redirects import router as redirects_router
app = FastAPI()

app.include_router(urls_router)
app.include_router(redirects_router)