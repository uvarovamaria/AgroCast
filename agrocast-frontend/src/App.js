// src/App.js
import React, { useState } from "react";
import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";
import "./App.css";
import MapPicker from "./components/MapPicker";
import Info from "./components/Info";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

// Упрощённый статус влаги для фермера
function getWaterStatus(spi) {
  if (spi === null || spi === undefined || Number.isNaN(spi)) {
    return { label: "нет данных", mood: "unknown", description: "" };
  }
  if (spi <= -0.5) {
    return {
      label: "Мало влаги",
      mood: "dry",
      description: "Почве не хватает влаги, растения могут испытывать стресс.",
    };
  }
  if (spi < 0.5) {
    return {
      label: "Влаги достаточно",
      mood: "ok",
      description: "Условия близки к норме для этого времени.",
    };
  }
  return {
    label: "Слишком влажно",
    mood: "wet",
    description:
      "Почва переувлажнена, возрастает риск заболеваний и переуплотнения.",
  };
}

// Сокращённая текстовая категория по многолетнему описанию
function simplifyCategory(category) {
  if (!category) return "нет данных";
  const text = category.toLowerCase();
  if (text.includes("засух")) return "Сухо";
  if (text.includes("норма")) return "Норма";
  if (text.includes("влаж")) return "Влажно";
  return category;
}

function App() {
  const [lat, setLat] = useState(47.0188);
  const [lon, setLon] = useState(39.9324);
  const [scaleMonths, setScaleMonths] = useState(3);
  const [historyYears, setHistoryYears] = useState(5);
  const [forecastDays, setForecastDays] = useState(7);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState("");
  const [forecast, setForecast] = useState(null);

  const [multi, setMulti] = useState(null);
  const [multiError, setMultiError] = useState("");

  const [page, setPage] = useState("main");

  // модалка с подробностями SARIMA-прогноза
  const [isSarimaModalOpen, setIsSarimaModalOpen] = useState(false);

  // -------------------------------
  // Запрос текущего SPI (+ SARIMA прогноз внутри ответа)
  // -------------------------------
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    setMulti(null);
    setMultiError("");

    try {
      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        scale_months: String(scaleMonths),
        history_years: String(historyYears),
      });

      const response = await fetch(`${API_BASE_URL}/spi/by-coords?${params}`);

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail =
          data && data.detail ? data.detail : "Ошибка запроса SPI";
        throw new Error(detail);
      }

      const data = await response.json();
      setResult(data);

      // параллельно тянем многомасштабный SPI (1, 3, 6 месяцев)
      try {
        const multiParams = new URLSearchParams({
          lat: String(lat),
          lon: String(lon),
          history_years: String(historyYears),
        });
        [1, 3, 6].forEach((s) => multiParams.append("scales", String(s)));

        const multiResp = await fetch(
          `${API_BASE_URL}/spi/multi-by-coords?${multiParams.toString()}`
        );
        if (!multiResp.ok) {
          const mdata = await multiResp.json().catch(() => null);
          const mdetail =
            mdata && mdata.detail
              ? mdata.detail
              : "Ошибка запроса многомасштабного SPI";
          throw new Error(mdetail);
        }
        const multiData = await multiResp.json();
        setMulti(multiData);
      } catch (err) {
        console.error(err);
        setMultiError(
          err.message || "Не удалось получить SPI за несколько периодов"
        );
      }
    } catch (err) {
      setError(err.message || "Неизвестная ошибка");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------
  // Запрос краткосрочного прогноза SPI (Open-Meteo)
  // -------------------------------
  const handleForecast = async () => {
    setForecastLoading(true);
    setForecastError("");
    setForecast(null);

    try {
      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        scale_months: String(scaleMonths),
        history_years: String(historyYears),
        forecast_days: String(forecastDays),
      });

      const response = await fetch(
        `${API_BASE_URL}/spi/forecast-by-coords?${params}`
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail =
          data && data.detail ? data.detail : "Ошибка запроса прогноза SPI";
        throw new Error(detail);
      }

      const data = await response.json();
      setForecast(data);
    } catch (err) {
      setForecastError(err.message || "Неизвестная ошибка");
    } finally {
      setForecastLoading(false);
    }
  };

  // История SPI
  const historyData =
    result?.history?.map((item) => ({
      date: item.date,
      spi: item.spi,
    })) || [];

  // Краткосрочный прогноз (Open-Meteo)
  const forecastData =
    forecast?.forecast?.map((item) => ({
      date: item.date,
      spi: item.spi,
      category: item.category,
    })) || [];

  const multiItems =
    multi?.items?.map((item) => ({
      scale: item.scale_months,
      spi: item.spi,
      category: item.category,
      shortCategory: simplifyCategory(item.category),
    })) || [];

  const status = getWaterStatus(result?.spi);

  // данные для мини-графика SARIMA в модалке (сейчас / через 30 дней)
  const sarimaMiniData =
    result?.forecast && typeof result.spi === "number"
      ? [
          {
            name: "Сейчас",
            label: "Сегодня",
            spi: result.spi,
          },
          {
            name: "Через 30 дней",
            label: "Прогноз",
            spi: result.forecast.spi_30,
          },
        ]
      : [];

  const sarimaDelta =
    result?.forecast && typeof result.spi === "number"
      ? result.forecast.spi_30 - result.spi
      : null;

  let sarimaDeltaText = "";
  if (sarimaDelta !== null) {
    if (sarimaDelta > 0.2) {
      sarimaDeltaText = "Ожидается повышение обеспеченности влагой.";
    } else if (sarimaDelta < -0.2) {
      sarimaDeltaText = "Ожидается уменьшение обеспеченности влагой.";
    } else {
      sarimaDeltaText = "Сильных изменений по влаге в среднем не ожидается.";
    }
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>AgroCast</h1>
        <p>Система климатического анализа и поддержки решений для сельского хозяйства</p>
      </header>

      <nav className="top-menu">
        <button
          className={page === "main" ? "menu-btn active" : "menu-btn"}
          onClick={() => setPage("main")}
        >
          Анализ поля
        </button>

        <button
          className={page === "info" ? "menu-btn active" : "menu-btn"}
          onClick={() => setPage("info")}
        >
          Что это значит?
        </button>
      </nav>

      {page === "info" ? (
        <Info />
      ) : (
        <main className="app-main">
          {/* Верхний блок: карта + параметры */}
          <div className="top-grid">
            {/* Карта */}
            <section className="card card--map">
              <div className="card-header">
                <h2>Выберите поле на карте</h2>
                <p className="card-subtitle">
                  Нажмите по карте — координаты подставятся автоматически.
                </p>
              </div>
              <div className="map-wrapper">
                <MapPicker
                  lat={lat}
                  lon={lon}
                  onSelect={(newLat, newLon) => {
                    setLat(newLat);
                    setLon(newLon);
                  }}
                />
              </div>
              <div className="coords-line">
                Текущая точка:{" "}
                <strong>
                  {lat.toFixed(4)}, {lon.toFixed(4)}
                </strong>
              </div>
            </section>

            {/* Параметры расчёта */}
            <section className="card card--controls">
              <div className="card-header">
                <h2>Параметры расчёта</h2>
                <p className="card-subtitle">
                  Обычно достаточно оставить значения по умолчанию.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="form-grid">
                <div className="form-group">
                  <label>Широта</label>
                  <input
                    type="number"
                    step="0.000001"
                    value={lat}
                    onChange={(e) => setLat(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label>Долгота</label>
                  <input
                    type="number"
                    step="0.000001"
                    value={lon}
                    onChange={(e) => setLon(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label>Период анализа (месяцев)</label>
                  <input
                    type="number"
                    min={1}
                    max={24}
                    value={scaleMonths}
                    onChange={(e) => setScaleMonths(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label>История для анализа (лет)</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={historyYears}
                    onChange={(e) => setHistoryYears(Number(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label>Прогноз на (дней)</label>
                  <input
                    type="number"
                    min={1}
                    max={16}
                    value={forecastDays}
                    onChange={(e) => setForecastDays(Number(e.target.value))}
                  />
                </div>

                <div className="form-actions">
                  <button type="submit" disabled={loading}>
                    {loading ? "Считаем..." : "Проанализировать влажность"}
                  </button>
                  <button
                    type="button"
                    onClick={handleForecast}
                    disabled={forecastLoading}
                  >
                    {forecastLoading
                      ? "Загружаем прогноз..."
                      : "Показать детальный прогноз"}
                  </button>
                </div>
              </form>

              {error && <div className="error-box">Ошибка: {error}</div>}
              {forecastError && (
                <div className="error-box">Ошибка прогноза: {forecastError}</div>
              )}
              {multiError && (
                <div className="error-box">Предупреждение: {multiError}</div>
              )}
            </section>
          </div>

          {/* Основной результат */}
          {result && (
            <section className="card">
              <div className="card-header">
                <h2>Состояние влаги на поле</h2>
              </div>

              <div className="status-block">
                <div className={`status-pill status-pill--${status.mood}`}>
                  <span className="status-emoji">
                    {status.mood === "dry"
                      ? "🌵"
                      : status.mood === "ok"
                      ? "✅"
                      : status.mood === "wet"
                      ? "💧"
                      : "ℹ️"}
                  </span>
                  <span className="status-text">{status.label}</span>
                </div>
                {status.description && (
                  <p className="status-description">{status.description}</p>
                )}
              </div>

              <div className="info-grid">
                <div>
                  <strong>Координаты:</strong>{" "}
                  {result.lat.toFixed(4)}, {result.lon.toFixed(4)}
                </div>
                <div>
                  <strong>Период для SPI:</strong> {result.scale_months} мес.
                </div>
                <div>
                  <strong>Дата окончания периода:</strong> {result.end_date}
                </div>
                <div>
                  <strong>Значение SPI:</strong> {result.spi.toFixed(2)} (
                  {result.category})
                </div>
              </div>

                {multiItems.length > 0 && (
                <div className="multi-scale">
                  <h3>Какой была влага за прошлые периоды</h3>
                  <p className="multi-caption">
                    Здесь показано, насколько сухо или влажно было в среднем за{" "}
                    <strong>последние 1, 3 и 6 месяцев</strong> до даты{" "}
                    <strong>{result.end_date}</strong>. 
                  </p>
                  <div className="multi-chips">
                    {multiItems.map((item) => (
                      <div key={item.scale} className="multi-chip">
                        <div className="multi-chip-scale">
                          За последние {item.scale} мес.
                        </div>
                        <div className="multi-chip-status">
                          {item.shortCategory}
                        </div>
                        <div className="multi-chip-spi">
                          SPI {item.spi.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Array.isArray(result.recommendations) &&
                result.recommendations.length > 0 && (
                  <div className="advice-box">
                    <h3>Рекомендации на сегодня</h3>
                    <ul>
                      {result.recommendations.map((text, idx) => (
                        <li key={idx}>{text}</li>
                      ))}
                    </ul>
                  </div>
                )}
            </section>
          )}

          {/* Долгосрочный прогноз (SARIMA) */}
          {result?.forecast && (
            <section className="card">
              <div className="card-header sarima-header">
                <div>
                  <h2>Прогноз состояния влаги на месяц</h2>
                  <p className="card-subtitle">
                    На основе динамики SPI за прошлые годы.
                  </p>
                </div>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setIsSarimaModalOpen(true)}
                >
                  <span className="link-button-icon">📈</span>
                  <span>Подробнее о прогнозе</span>
                </button>

              </div>
              <div className="info-grid">
                <div>
                  <strong>SPI сейчас:</strong> {result.spi.toFixed(2)} (
                  {result.category})
                </div>
                <div>
                  <strong>SPI через 30 дней (SARIMA):</strong>{" "}
                  {result.forecast.spi_30.toFixed(2)} (
                  {result.forecast.category})
                </div>
              </div>

              {sarimaDeltaText && (
                <p className="sarima-delta-text">{sarimaDeltaText}</p>
              )}

              {Array.isArray(result.forecast.recommendations) &&
                result.forecast.recommendations.length > 0 && (
                  <div className="advice-box">
                    <h3>Как подготовиться</h3>
                    <ul>
                      {result.forecast.recommendations.map((text, idx) => (
                        <li key={idx}>{text}</li>
                      ))}
                    </ul>
                  </div>
                )}
            </section>
          )}

          {/* История SPI */}
          <section className="card">
            <div className="card-header">
              <h2>История изменений влаги (SPI)</h2>
              <p className="card-subtitle">
                Помогает понять, был ли год более сухим или влажным, чем обычно.
              </p>
            </div>
            {historyData.length === 0 ? (
              <p>Исторических данных нет. Выполните расчёт SPI.</p>
            ) : (
              <>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={historyData}>
                      <defs>
                        <linearGradient
                          id="historyGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#4f46e5" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                      <Area
                        type="monotone"
                        dataKey="spi"
                        name="SPI"
                        fill="url(#historyGradient)"
                        stroke="none"
                        fillOpacity={0.6}
                      />
                      <Line
                        type="monotone"
                        dataKey="spi"
                        name="SPI"
                        dot={false}
                        stroke="#4f46e5"
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>SPI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyData.map((row, idx) => (
                        <tr key={idx}>
                          <td>{row.date}</td>
                          <td>{row.spi.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>

          {/* Краткосрочный прогноз (Open-Meteo) */}
          <section className="card">
            <div className="card-header">
              <h2>Прогноз на ближайшие дни</h2>
              <p className="card-subtitle">
                Что будет с влагой в ближайшие {forecastDays} дней по прогнозу
                погоды.
              </p>
            </div>
            {!forecast ? (
              <p>
                Нажмите «Показать детальный прогноз», чтобы увидеть ожидаемую
                динамику.
              </p>
            ) : forecast.forecast.length === 0 ? (
              <p>Прогнозных данных нет для заданных параметров.</p>
            ) : (
              <>
                <div className="info-grid">
                  <div>
                    <strong>Текущий SPI:</strong>{" "}
                    {forecast.latest_spi.toFixed(2)}{" "}
                    ({forecast.latest_category})
                  </div>
                  <div>
                    <strong>Горизонт прогноза:</strong>{" "}
                    {forecast.forecast_days} дней
                  </div>
                </div>

                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={forecastData}>
                      <defs>
                        <linearGradient
                          id="forecastGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop offset="0%" stopColor="#22c55e" stopOpacity={0.5} />
                          <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                      <Area
                        type="monotone"
                        dataKey="spi"
                        name="SPI (прогноз)"
                        fill="url(#forecastGradient)"
                        stroke="none"
                        fillOpacity={0.6}
                      />
                      <Line
                        type="monotone"
                        dataKey="spi"
                        name="SPI (прогноз)"
                        dot={true}
                        stroke="#16a34a"
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>SPI (прогноз)</th>
                        <th>Категория</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.forecast.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.date}</td>
                          <td>{item.spi.toFixed(2)}</td>
                          <td>{item.category}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        </main>
      )}

      {/* Модальное окно с подробным разбором SARIMA-прогноза */}
      {isSarimaModalOpen && result?.forecast && (
        <div className="modal-overlay" onClick={() => setIsSarimaModalOpen(false)}>
          <div
            className="modal"
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <div className="modal-header">
              <h2>Подробности прогноза SPI на месяц</h2>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setIsSarimaModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <p className="modal-intro">
              Этот прогноз построен по ряду SPI за предыдущие годы с помощью
              статистической модели SARIMA. Ниже показано, как меняется индекс
              от текущего значения к ожидаемому через 30 дней.
            </p>

            <div className="modal-grid">
              <div className="modal-value-block">
                <div className="modal-value-label">SPI сейчас</div>
                <div className="modal-value-number">
                  {result.spi.toFixed(2)}
                </div>
                <div className="modal-value-caption">{result.category}</div>
              </div>
              <div className="modal-value-block">
                <div className="modal-value-label">SPI через 30 дней</div>
                <div className="modal-value-number">
                  {result.forecast.spi_30.toFixed(2)}
                </div>
                <div className="modal-value-caption">
                  {result.forecast.category}
                </div>
              </div>
              {sarimaDelta !== null && (
                <div className="modal-value-block">
                  <div className="modal-value-label">Изменение SPI</div>
                  <div className="modal-value-number">
                    {sarimaDelta >= 0 ? "+" : ""}
                    {sarimaDelta.toFixed(2)}
                  </div>
                  <div className="modal-value-caption">{sarimaDeltaText}</div>
                </div>
              )}
            </div>

            {sarimaMiniData.length === 2 && (
              <div className="modal-chart">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={sarimaMiniData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                    <Line
                      type="monotone"
                      dataKey="spi"
                      name="SPI"
                      stroke="#f97316"
                      strokeWidth={3}
                      dot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="modal-text-block">
              <h3>Как читать этот прогноз</h3>
              <ul>
                <li>
                  Если SPI уходит сильно в минус — это сигнал к более сухим
                  условиям и риску засухи.
                </li>
                <li>
                  Если индекс растёт и становится положительным — ожидаются более
                  влажные условия, повышается риск переувлажнения и болезней.
                </li>
                <li>
                  Небольшие колебания (изменение меньше ~0.2–0.3) обычно не
                  требуют резкой смены стратегии, но полезно следить за трендом.
                </li>
              </ul>
              <p>
                На защите проекта можно подчеркнуть, что это не просто
                погодный прогноз, а <strong>статистический анализ</strong> ряда
                SPI с учётом сезонности, который помогает заранее увидеть риск
                «засушливого» или «сыро» месяца.
              </p>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="modal-primary-btn"
                onClick={() => setIsSarimaModalOpen(false)}
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
