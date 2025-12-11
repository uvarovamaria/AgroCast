# backend/app/api/v1/spi.py

import datetime as dt
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.spi import (
    compute_spi_for_point,
    compute_spi_forecast_for_point,
    generate_recommendations,
    categorize_spi,
    forecast_spi,                    # SARIMA прогноз
    categorize_spi_forecast,         # Категория SARIMA прогноза
    generate_forecast_recommendations,  # Рекомендации SARIMA прогноза
    compute_multi_scale_spi_for_point,  # Новый расчёт SPI сразу для нескольких окон
)
from ...services.meteostat_client import MeteostatError
from ...services.open_meteo_client import ForecastError

router = APIRouter()


# ================================================================
# МОДЕЛИ ДЛЯ БАЗОВЫХ ОТВЕТОВ
# ================================================================

class SpiHistoryPoint(BaseModel):
    date: dt.date = Field(..., description="Дата, соответствующая окну сумм осадков")
    spi: float = Field(..., description="Значение SPI на эту дату")


class SpiSarimaForecast(BaseModel):
    spi_30: float = Field(..., description="Прогноз SPI на 30 дней вперёд")
    category: str = Field(..., description="Категория прогноза SPI-30")
    recommendations: List[str] = Field(..., description="Рекомендации на основе прогноза")


class SpiPointResponse(BaseModel):
    lat: float
    lon: float
    scale_months: int
    end_date: dt.date
    spi: float
    category: str
    history: List[SpiHistoryPoint]
    recommendations: List[str]
    forecast: SpiSarimaForecast     # SARIMA блок


class SpiForecastPoint(BaseModel):
    date: dt.date = Field(..., description="Дата конца окна для прогноза SPI")
    spi: float = Field(..., description="Прогнозируемое значение SPI")
    category: str = Field(..., description="Категория по прогнозному SPI")
    recommendations: List[str] = Field(..., description="Рекомендации с учётом прогнозируемых условий")


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


# ================================================================
# ДОПОЛНИТЕЛЬНЫЕ МОДЕЛИ ДЛЯ НОВЫХ ЭНДПОИНТОВ
# ================================================================

class SpiMultiScaleItem(BaseModel):
    scale_months: int = Field(..., description="Длительность окна в месяцах")
    spi: float = Field(..., description="Текущее значение SPI для этого окна")
    category: str = Field(..., description="Категория SPI для этого окна")


class SpiMultiScaleResponse(BaseModel):
    lat: float
    lon: float
    end_date: dt.date
    history_years: int
    items: List[SpiMultiScaleItem]


class SpiForecastSummaryResponse(BaseModel):
    lat: float
    lon: float
    scale_months: int
    history_years: int
    forecast_days: int
    end_date: dt.date
    latest_spi: float
    latest_category: str
    sarima_spi_30: float
    sarima_category: str
    sarima_recommendations: List[str]


# ================================================================
# ЭНДПОИНТ: ТЕКУЩЕЕ SPI + SARIMA ПРОГНОЗ (КАК БЫЛО)
# ================================================================

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

    # История SPI
    history = [
        SpiHistoryPoint(date=idx.date(), spi=float(val))
        for idx, val in spi_series.items()
    ]

    # Рекомендации по текущему SPI
    recs = generate_recommendations(spi_value)

    # -------------------------
    # SARIMA-прогноз SPI-30
    # -------------------------
    spi_30 = forecast_spi(spi_series)
    forecast_category = categorize_spi_forecast(spi_30)
    forecast_recs = generate_forecast_recommendations(spi_30)

    sarima_block = SpiSarimaForecast(
        spi_30=spi_30,
        category=forecast_category,
        recommendations=forecast_recs,
    )

    return SpiPointResponse(
        lat=lat,
        lon=lon,
        scale_months=scale_months,
        end_date=end_date or dt.date.today(),
        spi=spi_value,
        category=category,
        history=history,
        recommendations=recs,
        forecast=sarima_block,
    )


# ================================================================
# ЭНДПОИНТ: ПРОГНОЗ SPI ПО ОСАДКАМ (КАК БЫЛО)
# ================================================================

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

    # Формируем точки прогноза
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


# ================================================================
# НОВЫЙ ЭНДПОИНТ: SPI ДЛЯ НЕСКОЛЬКИХ ОКОН (1, 3, 6 МЕСЯЦЕВ И Т.Д.)
# ================================================================

@router.get("/multi-by-coords", response_model=SpiMultiScaleResponse)
async def get_spi_multi_by_coords(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    scales: List[int] = Query([1, 3, 6], description="Список окон SPI в месяцах"),
    history_years: int = Query(10, ge=1, le=50),
    end_date: dt.date | None = Query(None),
):
    try:
        multi = compute_multi_scale_spi_for_point(
            lat=lat,
            lon=lon,
            scales_months=scales,
            end_date=end_date,
            history_years=history_years,
        )
    except MeteostatError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка Meteostat: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    items = [
        SpiMultiScaleItem(
            scale_months=scale,
            spi=value["spi"],
            category=value["category"],
        )
        for scale, value in sorted(multi.items(), key=lambda kv: kv[0])
    ]

    return SpiMultiScaleResponse(
        lat=lat,
        lon=lon,
        end_date=end_date or dt.date.today(),
        history_years=history_years,
        items=items,
    )


# ================================================================
# НОВЫЙ ЭНДПОИНТ: КРАТКИЙ ИТОГ ПРОГНОЗА SPI (SARIMA)
# ================================================================

@router.get("/forecast-summary-by-coords", response_model=SpiForecastSummaryResponse)
async def get_spi_forecast_summary_by_coords(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    scale_months: int = Query(3, ge=1, le=24),
    history_years: int = Query(10, ge=1, le=50),
    forecast_days: int = Query(30, ge=1, le=60),
    end_date: dt.date | None = Query(None),
):
    """
    Краткий итог по точке: текущее SPI + SARIMA-прогноз SPI-30 и рекомендации.
    Использует те же данные, что и базовые эндпоинты.
    """
    try:
        # Берём исторический ряд SPI без прогноза осадков
        latest_spi, latest_category, spi_series = compute_spi_for_point(
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

    # SARIMA-прогноз
    spi_30 = forecast_spi(spi_series)
    forecast_category = categorize_spi_forecast(spi_30)
    forecast_recs = generate_forecast_recommendations(spi_30)

    return SpiForecastSummaryResponse(
        lat=lat,
        lon=lon,
        scale_months=scale_months,
        history_years=history_years,
        forecast_days=forecast_days,
        end_date=end_date or dt.date.today(),
        latest_spi=latest_spi,
        latest_category=latest_category,
        sarima_spi_30=spi_30,
        sarima_category=forecast_category,
        sarima_recommendations=forecast_recs,
    )
