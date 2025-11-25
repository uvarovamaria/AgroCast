from typing import Optional

import pandas as pd
import requests


class ForecastError(Exception):
    """Ошибка при работе с Open-Meteo."""
    pass


def fetch_daily_precipitation_forecast(
    lat: float,
    lon: float,
    days: int = 7,
    timezone: str = "UTC",
) -> pd.Series:
    """
    Получить прогноз суточных осадков (мм) по координатам на N дней вперёд
    с помощью Open-Meteo.

    Возвращает pandas.Series:
        index = Timestamp (дата),
        values = осадки в мм (float).
    """
    if days < 1 or days > 16:
        raise ValueError("days должен быть в диапазоне 1–16 (ограничение Open-Meteo)")

    base_url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "forecast_days": days,
        "timezone": timezone,
        "precipitation_unit": "mm",
    }

    try:
        resp = requests.get(base_url, params=params, timeout=10)
    except requests.RequestException as e:
        raise ForecastError(f"Ошибка запроса Open-Meteo: {e}")

    if resp.status_code != 200:
        raise ForecastError(f"Open-Meteo вернул код {resp.status_code}: {resp.text}")

    data = resp.json()
    daily = data.get("daily")
    if not daily:
        raise ForecastError("В ответе Open-Meteo нет блока 'daily'")

    times = daily.get("time")
    prcp = daily.get("precipitation_sum")

    if times is None or prcp is None:
        raise ForecastError("В daily Open-Meteo нет полей 'time' или 'precipitation_sum'")

    if len(times) != len(prcp):
        raise ForecastError("Размерности 'time' и 'precipitation_sum' не совпадают")

    series = pd.Series(prcp, index=pd.to_datetime(times))
    series = series.sort_index()

    return series
