# backend/app/api/v1/__init__.py

from fastapi import APIRouter

from .spi import router as spi_router
from .fields import router as fields_router

api_router = APIRouter()
api_router.include_router(spi_router, prefix="/spi", tags=["SPI"])
api_router.include_router(fields_router, prefix="/fields", tags=["Fields"])
