import datetime as dt

import numpy as np
import pandas as pd
from scipy.stats import norm, gamma

from .meteostat_client import fetch_daily_precipitation, MeteostatError
from .open_meteo_client import fetch_daily_precipitation_forecast, ForecastError

# -----------------------------
# Прогноз SPI на основе SARIMA
# -----------------------------

from statsmodels.tsa.statespace.sarimax import SARIMAX

def forecast_spi(spi_series: pd.Series, days: int = 30) -> float:
    """
    Прогноз SPI на N дней вперёд с помощью SARIMA.
    """
    # SARIMA требует регулярный временной ряд
    spi_series = spi_series.asfreq("D").interpolate()

    try:
        model = SARIMAX(
            spi_series,
            order=(1, 0, 1),
            seasonal_order=(1, 0, 1, 30),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        model_fit = model.fit(disp=False)
        forecast = model_fit.forecast(days)
        return float(forecast.iloc[-1])
    except Exception:
        # fallback если SARIMA не сошлась
        return float(spi_series.tail(30).mean())


def categorize_spi_forecast(spi: float) -> str:
    """Категория для прогноза SPI."""
    if spi <= -2:
        return "экстремальная засуха ожидается"
    if spi <= -1.5:
        return "сильная засуха ожидается"
    if spi <= -1:
        return "умеренная засуха ожидается"
    if spi < 1:
        return "нормальное состояние ожидается"
    if spi < 1.5:
        return "повышенная влажность ожидается"
    if spi < 2:
        return "сильная влажность ожидается"
    return "экстремальная влажность ожидается"


def generate_forecast_recommendations(spi_forecast: float) -> list[str]:
    """Рекомендации на основе прогноза SPI."""
    return generate_recommendations(spi_forecast)

# -----------------------------
# Генерация рекомендаций
# -----------------------------



def generate_recommendations(spi: float) -> list[str]:
    """Вернуть список рекомендаций в зависимости от SPI."""

    if spi <= -2:
        return [
            "Экстремальная засуха: увеличить орошение до максимума.",
            "Отложить посев — высокий риск гибели всходов.",
            "Не вносить удобрения: эффективность резко снижена.",
            "Провести оценку стресса растений.",
        ]

    if spi <= -1.5:
        return [
            "Сильная засуха: перейти на щадящий режим обработки почвы.",
            "Запланировать полив на ближайшие дни.",
            "Отложить механическую обработку посевов.",
        ]

    if spi <= -1.0:
        return [
            "Умеренная засуха: усиливать мониторинг состояния посевов.",
            "Минимизировать нагрузку на почву тяжелой техникой.",
            "Оценить возможность дополнительного орошения.",
        ]

    if spi < 1.0:
        return [
            "Норма: возможен стандартный режим агротехнических работ.",
            "Проводите подкормки и обработку почвы по графику.",
            "Следите за направлением тренда SPI.",
        ]

    if spi < 1.5:
        return [
            "Умеренно влажно: снизить или отключить орошение.",
            "Увеличить мониторинг грибковых заболеваний.",
        ]

    if spi < 2.0:
        return [
            "Сильно влажно: высокий риск появления болезней.",
            "Рекомендована фунгицидная обработка.",
            "Избегать использования тяжелой техники.",
        ]

    return [
        "Экстремальная влажность: возможно заболачивание.",
        "Перенести полевые работы, кроме мониторинга.",
        "Высокий риск ухудшения качества урожая.",
    ]


# -----------------------------
# Вспомогательная категоризация
# -----------------------------

def categorize_spi(spi: float) -> str:
    """Вернуть текстовую категорию по значению SPI."""
    if spi <= -2:
        return "экстремальная засуха"
    if spi <= -1.5:
        return "сильная засуха"
    if spi <= -1:
        return "умеренная засуха"
    if spi < 1:
        return "в пределах нормы"
    if spi < 1.5:
        return "умеренно влажно"
    if spi < 2:
        return "сильно влажно"
    return "экстремально влажно"


# -----------------------------
# Вспомогательная функция: расчёт SPI по ряду сумм осадков
# -----------------------------

def _compute_spi_series_from_sums(
    rolling_sums: pd.Series,
) -> tuple[pd.Series, float]:
    """
    По ряду сумм осадков (rolling_sums) считает ряд SPI.

    Логика:
    - Для оценки гамма-распределения берём только strictly > 0.
    - Для окон с суммой <= 0 SPI не считаем (NaN), чтобы не было
      искусственного плато на уровне ≈ -4.75.
    """

    # Убираем NaN, но сохраняем индекс
    rolling_clean = rolling_sums.dropna()

    if len(rolling_clean) < 30:
        raise ValueError("Недостаточно данных для расчёта SPI")

    # Для фита используем только строго положительные значения
    rolling_pos = rolling_clean[rolling_clean > 0]

    if len(rolling_pos) < 30:
        raise ValueError(
            "Недостаточно ненулевых данных осадков для статистически устойчивого "
            "расчёта SPI (почти нет осадков за выбранный период)."
        )

    if rolling_pos.nunique() == 1:
        raise ValueError(
            "Слишком мало вариации в данных осадков для расчёта SPI "
            "(все суммы осадков почти одинаковы)."
        )

    # Оцениваем параметры гамма-распределения
    try:
        shape, loc, scale = gamma.fit(rolling_pos, floc=0)
    except Exception as e:
        raise ValueError(f"Не удалось аппроксимировать распределение осадков: {e}")

    # Создаём пустой ряд SPI с тем же индексом
    spi_series = pd.Series(index=rolling_clean.index, dtype=float)

    # Считаем SPI только там, где суммы > 0
    mask = rolling_clean > 0
    if mask.sum() == 0:
        raise ValueError("Все суммы осадков равны нулю, расчёт SPI невозможен.")

    cdf_vals = gamma.cdf(rolling_clean[mask], shape, loc=loc, scale=scale)
    # Подстраховка от 0 и 1
    cdf_vals = np.clip(cdf_vals, 1e-6, 1 - 1e-6)

    spi_series[mask] = norm.ppf(cdf_vals)

    # Последнее валидное значение SPI
    last_valid = spi_series.dropna()
    if last_valid.empty:
        raise ValueError("Не удалось получить валидные значения SPI")

    latest_spi = float(last_valid.iloc[-1])

    return spi_series, latest_spi


# -----------------------------
# Основной расчёт SPI (история + текущее)
# -----------------------------

def compute_spi_for_point(
    lat: float,
    lon: float,
    scale_months: int = 3,
    end_date: dt.date | None = None,
    history_years: int = 10,
):
    """Рассчитать SPI и исторический ряд по координатам (без прогноза)."""

    if end_date is None:
        end_date = dt.date.today()

    start_date = end_date - dt.timedelta(days=history_years * 365)

    # 1. Сырые суточные осадки
    prcp_series = fetch_daily_precipitation(lat, lon, start_date, end_date)

    # 2. Скользящая сумма осадков за окно scale_months (грубая оценка 30 дней на месяц)
    rolling_window_days = scale_months * 30
    rolling = prcp_series.rolling(window=rolling_window_days).sum()

    # 3. Считаем SPI по ряду сумм
    spi_series, latest_spi = _compute_spi_series_from_sums(rolling)

    category = categorize_spi(latest_spi)

    return latest_spi, category, spi_series


# -----------------------------
# Расчёт SPI с учётом прогноза
# -----------------------------

def compute_spi_forecast_for_point(
    lat: float,
    lon: float,
    scale_months: int = 3,
    end_date: dt.date | None = None,
    history_years: int = 10,
    forecast_days: int = 7,
):
    """
    Рассчитать прогноз SPI на несколько дней вперёд.

    Логика:
    - Берём исторические суточные осадки (Meteostat)
    - Берём прогноз суточных осадков (Open-Meteo)
    - Склеиваем, считаем скользящие суммы
    - Параметры gamma-фита оцениваем ТОЛЬКО по историческим положительным окнам
    - Считаем SPI и возвращаем:
        - последнее историческое значение
        - исторический ряд
        - прогнозный ряд (на forecast_days вперёд)
    """

    if end_date is None:
        end_date = dt.date.today()

    if forecast_days < 1 or forecast_days > 16:
        raise ValueError("forecast_days должен быть в диапазоне 1–16")

    start_date = end_date - dt.timedelta(days=history_years * 365)

    # Исторические осадки
    prcp_hist = fetch_daily_precipitation(lat, lon, start_date, end_date)

    # Прогноз осадков (Open-Meteo даёт с сегодняшнего дня)
    prcp_forecast = fetch_daily_precipitation_forecast(
        lat=lat,
        lon=lon,
        days=forecast_days,
        timezone="UTC",
    )

    # Берём только дни строго после end_date, чтобы не дублировать
    prcp_forecast = prcp_forecast[prcp_forecast.index.date > end_date]

    if prcp_forecast.empty:
        raise ValueError("Open-Meteo не вернул прогноз осадков после указанной end_date")

    # На всякий случай ограничим до forecast_days элементов
    prcp_forecast = prcp_forecast.iloc[:forecast_days]

    # Склеиваем историю + прогноз
    prcp_combined = pd.concat([prcp_hist, prcp_forecast])
    prcp_combined = prcp_combined.sort_index()

    rolling_window_days = scale_months * 30
    rolling_all = prcp_combined.rolling(window=rolling_window_days).sum()

    # Для фита используем только историческую часть окон
    rolling_hist = rolling_all[rolling_all.index.date <= end_date]

    # Считаем SPI по всем суммам, но последнюю точку и разбиение делаем сами
    spi_all, latest_spi = _compute_spi_series_from_sums(rolling_hist.combine_first(rolling_all))

    # Исторический SPI (до end_date)
    spi_hist = spi_all[spi_all.index.date <= end_date].dropna()

    # Прогнозный SPI (после end_date)
    spi_forecast = spi_all[spi_all.index.date > end_date].dropna()
    spi_forecast = spi_forecast.iloc[:forecast_days]

    if spi_hist.empty:
        raise ValueError("Не удалось получить исторические значения SPI")

    latest_category = categorize_spi(latest_spi)

    return latest_spi, latest_category, spi_hist, spi_forecast
