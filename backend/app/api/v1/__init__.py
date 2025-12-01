from fastapi import APIRouter
from .spi import router as spi_router

api_router = APIRouter()
api_router.include_router(spi_router, prefix="/spi", tags=["SPI"])
