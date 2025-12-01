from datetime import date, datetime
from typing import Optional

import pandas as pd
from meteostat import Point, Daily


class MeteostatError(Exception):
    """Ошибка при работе с Meteostat."""
    pass


def fetch_daily_precipitation(
    lat: float,
    lon: float,
    start: date,
    end: date,
    alt: Optional[float] = None,
) -> pd.Series:
    """
    Получить ежедневные осадки (мм) по координатам в заданном диапазоне дат,
    используя библиотеку meteostat.

    Возвращает pandas.Series:
        index = Timestamp (дата),
        values = осадки в мм (float).

    ВАЖНО:
    - Пропуски (NaN) мы считаем отсутствием данных и удаляем.
    - Никаких fillna(0.0), чтобы дыры в данных не выглядели как
      "многолетний нулевой дождь".
    """

    # Meteostat ожидает datetime, используем полночь по UTC
    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day)

    # Точка по координатам (alt можно не задавать)
    point = Point(lat, lon, alt if alt is not None else 0)

    try:
        daily = Daily(point, start_dt, end_dt)
        df = daily.fetch()
    except Exception as e:
        raise MeteostatError(f"Ошибка при запросе данных Meteostat: {e}")

    if df.empty:
        raise MeteostatError("Meteostat вернул пустой набор данных")

    # По документации meteostat, осадки в столбце 'prcp' (мм)
    if "prcp" not in df.columns:
        raise MeteostatError("В данных Meteostat отсутствует столбец 'prcp' с осадками")

    # Берём столбец осадков, приводим к float
    series = df["prcp"].astype(float)

    # Пропуски считаем отсутствием измерений, а не "0 мм" → удаляем
    series = series.dropna()

    # На всякий случай отбрасываем отрицательные значения (если вдруг
    # из-за округлений появились небольшие минусы)
    series = series.clip(lower=0.0)

    # Сортируем по дате
    series = series.sort_index()

    if series.empty:
        raise MeteostatError(
            "После удаления пропусков набор осадков пуст. "
            "Недостаточно данных для расчёта."
        )

    return series
