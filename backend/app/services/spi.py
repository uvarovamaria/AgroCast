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


# -----------------------------------------------------------------------------
# Классификация SPI (факт и прогноз)
# -----------------------------------------------------------------------------


def categorize_spi(spi: float) -> str:
    """
    Классификация SPI по шкале «очень сухо / сухо / норма / влажно».
    Используется и для текущих значений, и для прогнозов.
    """
    if spi <= -2.0:
        return "экстремальная засуха"
    elif spi <= -1.5:
        return "сильная засуха"
    elif spi <= -1.0:
        return "умеренная засуха"
    elif spi <= -0.5:
        return "слабо засушливые условия"
    elif spi < 0.5:
        return "норма по влажности"
    elif spi < 1.0:
        return "слабо влажные условия"
    elif spi < 1.5:
        return "умеренно влажные условия"
    else:
        return "очень влажные условия"


def categorize_spi_forecast(spi: float) -> str:
    """
    Для единообразия используем ту же шкалу, что и для фактического SPI.
    Если нужно, фронт может отдельно добавить слово «ожидается».
    """
    return categorize_spi(spi)


# -----------------------------------------------------------------------------
# Рекомендации по текущему SPI
# -----------------------------------------------------------------------------


def generate_recommendations(spi: float) -> list[str]:
    """
    Агрономические рекомендации на основе текущего SPI.
    Без привязки к конкретной культуре, чтобы можно было использовать «как есть».
    """
    recs: list[str] = []

    # Экстремальная засуха
    if spi <= -2.0:
        recs.append(
            "Фиксируется экстремальный дефицит влаги. В первую очередь имеет смысл "
            "сосредоточиться на сохранении почвенной влаги: минимизировать количество "
            "проходов техники, отказаться от лишних обработок, сохранять растительные остатки."
        )
        recs.append(
            "При наличии орошения обязательно проверить фактическую влажность почвы и, "
            "при подтверждении нехватки влаги, перейти на приоритетный полив наиболее "
            "важных полей, вместо равномерного распределения воды."
        )
        recs.append(
            "Пересмотрите планы по поздним затратным операциям (подкормки, обработки): "
            "их эффективность в условиях сильной засухи существенно ниже."
        )

    # Сильная засуха
    elif spi <= -1.5:
        recs.append(
            "Отмечается сильная засуха: осадков за период значительно меньше нормы. "
            "Усилить контроль состояния посевов и почвы, особенно в наиболее чувствительных фазах."
        )
        recs.append(
            "Если используется орошение, стоит скорректировать график поливов: "
            "сделать акцент на полях, где сейчас проходят ключевые этапы формирования урожая."
        )
        recs.append(
            "Избегайте тяжёлых механических обработок, дополнительно пересушивающих верхний слой почвы."
        )

    # Умеренная засуха
    elif spi <= -1.0:
        recs.append(
            "Умеренный дефицит влаги: количество осадков заметно ниже обычного. "
            "Рекомендуется чаще оценивать влажность почвы и внимательно следить за признаками стресса растений."
        )
        recs.append(
            "Планируя подкормки и обработки, учитывайте, что эффективность при дефиците влаги ниже: "
            "не стоит завышать ожидания по прибавке урожайности."
        )
        recs.append(
            "По возможности ограничьте лишние проходы техники, чтобы не ухудшать структуру почвы."
        )

    # Слабо засушливые условия
    elif spi <= -0.5:
        recs.append(
            "Условия немного суше нормы. Пока существенного стресса может не быть, "
            "но стоит взять влагу под более плотный контроль."
        )
        recs.append(
            "Имеет смысл заранее продумать, как вы будете действовать при дальнейшем ухудшении ситуации: "
            "какие поля и работы будут в приоритете при продолжающемся снижении обеспеченности влагой."
        )

    # Норма
    elif spi < 0.5:
        recs.append(
            "Влажность близка к статистической норме для этого периода. "
            "Можно придерживаться стандартной технологии выращивания."
        )
        recs.append(
            "Тем не менее, полезно фиксировать текущие параметры (влажность почвы, состояние посевов), "
            "чтобы сравнить их с будущими засушливыми или влажными периодами."
        )

    # Слабо влажные условия
    elif spi < 1.0:
        recs.append(
            "Условия немного более влажные, чем обычно. В большинстве случаев это благоприятно, "
            "но стоит учитывать, что на тяжёлых почвах возрастает риск переуплотнения при работе техникой."
        )
        recs.append(
            "При планировании заезда в поле проверяйте фактическую проходимость, "
            "чтобы не получить колейность и не ухудшить структуру почвы."
        )

    # Умеренно влажные условия
    elif spi < 1.5:
        recs.append(
            "Осадков больше нормы: умеренно влажные условия. "
            "На переувлажнённых участках стоит оценить состояние корневой системы и проветривание посевов."
        )
        recs.append(
            "В таких условиях выше риск развития грибных заболеваний, поэтому важно "
            "не пропускать осмотры и профилактические обработки по вашим регламентам."
        )

    # Очень влажные условия
    else:
        recs.append(
            "Очень влажные условия: осадков существенно больше нормы, "
            "возможны застой воды и подтопления пониженных мест."
        )
        recs.append(
            "По возможности ограничьте работу тяжёлой техники до подсыхания почвы, "
            "чтобы не вызвать длительное переуплотнение и не ухудшить структуру."
        )
        recs.append(
            "Усилите мониторинг болезней и состояния корневой системы, "
            "особенно на участках с плохим дренажем."
        )

    return recs


# -----------------------------------------------------------------------------
# Рекомендации по прогнозному SPI (SARIMA или по осадкам)
# -----------------------------------------------------------------------------


def generate_forecast_recommendations(spi_forecast: float) -> list[str]:
    """
    Рекомендации на ближайший период (обычно 30 дней) по прогнозному SPI.
    Логика похожа на generate_recommendations, но с акцентом на планирование.
    """
    recs: list[str] = []

    # Экстремальная засуха впереди
    if spi_forecast <= -2.0:
        recs.append(
            "Прогноз указывает на очень сильный дефицит влаги в ближайший период. "
            "Имеет смысл заранее определить поля, которые будут в приоритете по воде и ресурсам, "
            "и скорректировать планы работ с учётом возможного снижения урожайности."
        )
        recs.append(
            "Проверьте, нет ли затратных операций (обработки, подкормки), эффективность которых "
            "в условиях сильной засухи будет значительно ниже. Их можно перенести или сократить."
        )

    # Сильная засуха
    elif spi_forecast <= -1.5:
        recs.append(
            "Ожидается сильный дефицит влаги. Стоит заранее оценить, "
            "хватит ли ресурсов (вода, техника, люди) для возможного усиления поливов или "
            "для изменения графика полевых работ."
        )
        recs.append(
            "Полезно заранее обсудить внутри хозяйства сценарий «засушливого года»: "
            "какие поля будут получать больше внимания, а какие останутся на базовой технологии."
        )

    # Умеренная засуха
    elif spi_forecast <= -1.0:
        recs.append(
            "Прогнозируется умеренный дефицит влаги. Это сигнал заранее продумать приоритеты: "
            "какие участки наиболее чувствительны к недополиву и в какие сроки."
        )
        recs.append(
            "Можно уже сейчас подготовить план корректировки поливов и переноса части работ, "
            "если фактическая погода подтвердит прогноз."
        )

    # Слабо засушливые условия
    elif spi_forecast <= -0.5:
        recs.append(
            "Прогноз показывает тенденцию к более сухим условиям. "
            "Пока это не критично, но при продолжении тренда стоит быть готовыми к ужесточению."
        )
        recs.append(
            "Имеет смысл заранее предусмотреть, какие мероприятия будут пересмотрены в первую очередь, "
            "если дефицит влаги усилится (например, часть обработок и поздних подкормок)."
        )

    # Норма
    elif spi_forecast < 0.5:
        recs.append(
            "Прогнозируемая обеспеченность влагой близка к норме. Можно планировать работы в обычном режиме."
        )
        recs.append(
            "Тем не менее, стоит отслеживать обновление прогноза: при резком изменении тенденции "
            "в сторону засухи или переувлажнения планы можно скорректировать заранее."
        )

    # Слабо влажные условия
    elif spi_forecast < 1.0:
        recs.append(
            "Ожидаются слегка повышенные осадки. Обычно это не создаёт серьёзных проблем, "
            "но график работ в поле лучше планировать с запасом по времени на возможные дожди."
        )
        recs.append(
            "Учитывайте, что при частых осадках будет меньше «окон», когда техника может зайти в поле без ущерба для почвы."
        )

    # Умеренно влажные условия
    elif spi_forecast < 1.5:
        recs.append(
            "Прогнозируется период с осадками выше нормы. "
            "Рекомендуется заранее продумать, как будете использовать короткие сухие окна для ключевых операций."
        )
        recs.append(
            "Также стоит предусмотреть усиленный мониторинг болезней, так как влажные условия "
            "часто сопровождаются повышенным инфекционным фоном."
        )

    # Очень влажные условия
    else:
        recs.append(
            "В ближайший период возможны очень влажные условия, в отдельные дни — застой воды. "
            "Планируя работы, закладывайте вероятность простоев из-за дождей и непролазной почвы."
        )
        recs.append(
            "Обратите внимание на участки с плохим дренажем: там выше риск выпада растений и проблем с корневой системой."
        )

    return recs


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


# -----------------------------------------------------------------
# Дополнительный расчёт: SPI сразу для нескольких масштабов
# -----------------------------------------------------------------


def compute_multi_scale_spi_for_point(
    lat: float,
    lon: float,
    scales_months: list[int],
    end_date: dt.date | None = None,
    history_years: int = 10,
) -> dict[int, dict[str, float]]:
    """
    Рассчитать SPI сразу для нескольких масштабов (1, 3, 6 месяцев и т.д.)
    по одной и той же истории осадков.

    Возвращает словарь:
        {
            scale_months: {
                "spi": float,
                "category": str,
            },
            ...
        }
    """
    if end_date is None:
        end_date = dt.date.today()

    if not scales_months:
        raise ValueError("Список scales_months не должен быть пустым")

    # Убираем дубликаты и сортируем, чтобы не считать одно и то же окно несколько раз
    unique_scales = sorted(set(scales_months))

    start_date = end_date - dt.timedelta(days=history_years * 365)

    # Одна выборка осадков для всех окон
    prcp_series = fetch_daily_precipitation(lat, lon, start_date, end_date)

    result: dict[int, dict[str, float]] = {}

    for scale in unique_scales:
        if scale < 1 or scale > 24:
            raise ValueError("scale_months должен быть в диапазоне 1–24")

        rolling_window_days = scale * 30
        rolling = prcp_series.rolling(window=rolling_window_days).sum()

        spi_series, latest_spi = _compute_spi_series_from_sums(rolling)
        category = categorize_spi(latest_spi)

        result[scale] = {
            "spi": float(latest_spi),
            "category": category,
        }

    return result
