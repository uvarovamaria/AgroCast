import datetime as dt
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.spi import (
    compute_spi_for_point,
    compute_spi_forecast_for_point,
    generate_recommendations,
    categorize_spi,
)
from ...services.meteostat_client import MeteostatError
from ...services.open_meteo_client import ForecastError

router = APIRouter()


# -----------------------------
# Модели ответа
# -----------------------------

class SpiHistoryPoint(BaseModel):
    date: dt.date = Field(..., description="Дата, соответствующая окну сумм осадков")
    spi: float = Field(..., description="Значение SPI на эту дату")


class SpiPointResponse(BaseModel):
    lat: float
    lon: float
    scale_months: int
    end_date: dt.date
    spi: float
    category: str
    history: List[SpiHistoryPoint]
    recommendations: List[str]


class SpiForecastPoint(BaseModel):
    date: dt.date = Field(..., description="Дата конца окна для прогноза SPI")
    spi: float = Field(..., description="Прогнозируемое значение SPI")
    category: str = Field(..., description="Категория по прогнозному SPI")
    recommendations: List[str] = Field(
        ...,
        description="Рекомендации с учётом прогнозируемых условий",
    )


class SpiForecastResponse(BaseModel):
    lat: float
    lon: float
    scale_months: int
    history_years: int
    end_date: dt.date
    forecast_days: int
    latest_spi: float
    latest_category: str
    forecast: List[SpiForecastPoint]


# -----------------------------
# Эндпоинт: текущее SPI по координатам
# -----------------------------

@router.get("/by-coords", response_model=SpiPointResponse)
async def get_spi_by_coords(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    scale_months: int = Query(3, ge=1, le=24),
    history_years: int = Query(10, ge=1, le=50),
    end_date: dt.date | None = Query(None),
):
    try:
        spi_value, category, spi_series = compute_spi_for_point(
            lat=lat,
            lon=lon,
            scale_months=scale_months,
            end_date=end_date,
            history_years=history_years,
        )
    except MeteostatError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка Meteostat: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    history = [
        SpiHistoryPoint(date=idx.date(), spi=float(val))
        for idx, val in spi_series.items()
    ]

    recs = generate_recommendations(spi_value)

    return SpiPointResponse(
        lat=lat,
        lon=lon,
        scale_months=scale_months,
        end_date=end_date or dt.date.today(),
        spi=spi_value,
        category=category,
        history=history,
        recommendations=recs,
    )


# -----------------------------
# Эндпоинт: прогноз SPI по координатам
# -----------------------------

@router.get("/forecast-by-coords", response_model=SpiForecastResponse)
async def get_spi_forecast_by_coords(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    scale_months: int = Query(3, ge=1, le=24),
    history_years: int = Query(10, ge=1, le=50),
    forecast_days: int = Query(7, ge=1, le=16),
    end_date: dt.date | None = Query(None),
):
    try:
        latest_spi, latest_category, spi_hist, spi_forecast = compute_spi_forecast_for_point(
            lat=lat,
            lon=lon,
            scale_months=scale_months,
            end_date=end_date,
            history_years=history_years,
            forecast_days=forecast_days,
        )
    except MeteostatError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка Meteostat: {e}")
    except ForecastError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка Open-Meteo: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    # Формируем список прогнозных точек
    forecast_points: List[SpiForecastPoint] = []
    for idx, val in spi_forecast.items():
        spi_val = float(val)
        cat = categorize_spi(spi_val)
        recs = generate_recommendations(spi_val)

        forecast_points.append(
            SpiForecastPoint(
                date=idx.date(),
                spi=spi_val,
                category=cat,
                recommendations=recs,
            )
        )

    return SpiForecastResponse(
        lat=lat,
        lon=lon,
        scale_months=scale_months,
        history_years=history_years,
        end_date=end_date or dt.date.today(),
        forecast_days=forecast_days,
        latest_spi=latest_spi,
        latest_category=latest_category,
        forecast=forecast_points,
    )
