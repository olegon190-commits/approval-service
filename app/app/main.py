"""approval-service: сервис согласования контента"""
from fastapi import FastAPI
from app.routers import approval, health
from app.database import engine
from app import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="approval-service",
    description="Сервис согласования контента перед публикацией",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(approval.router, prefix="/api/v1")
