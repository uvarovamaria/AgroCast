// src/App.js
import React, { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

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

  // -------------------------------
  // Запрос текущего SPI
  // -------------------------------
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

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
        const detail = data && data.detail ? data.detail : "Ошибка запроса SPI";
        throw new Error(detail);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Неизвестная ошибка");
    } finally {
      setLoading(false);
    }
  };

  // -------------------------------
  // Запрос прогноза SPI
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

  const historyData =
    result?.history?.map((item) => ({
      date: item.date,
      spi: item.spi,
    })) || [];

  const forecastData =
    forecast?.forecast?.map((item) => ({
      date: item.date,
      spi: item.spi,
      category: item.category,
    })) || [];

  return (
    <div className="App">
      <header className="app-header">
        <h1>AgroCast SPI</h1>
        <p>Оценка климатического риска по координатам</p>
      </header>

      <main className="app-main">
        {/* Форма параметров */}
        <section className="card">
          <h2>Параметры расчёта</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Широта (lat)</label>
              <input
                type="number"
                step="0.000001"
                value={lat}
                onChange={(e) => setLat(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>Долгота (lon)</label>
              <input
                type="number"
                step="0.000001"
                value={lon}
                onChange={(e) => setLon(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>Окно SPI (месяцев)</label>
              <input
                type="number"
                min={1}
                max={24}
                value={scaleMonths}
                onChange={(e) => setScaleMonths(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>История (лет)</label>
              <input
                type="number"
                min={1}
                max={50}
                value={historyYears}
                onChange={(e) => setHistoryYears(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>Прогноз (дней)</label>
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
                {loading ? "Расчёт..." : "Рассчитать текущий SPI"}
              </button>
              <button
                type="button"
                onClick={handleForecast}
                disabled={forecastLoading}
              >
                {forecastLoading ? "Загрузка прогноза..." : "Получить прогноз SPI"}
              </button>
            </div>
          </form>

          {error && <div className="error-box">Ошибка: {error}</div>}
          {forecastError && (
            <div className="error-box">Ошибка прогноза: {forecastError}</div>
          )}
        </section>

        {/* Текущий SPI */}
        {result && (
          <section className="card">
            <h2>Текущий индекс SPI</h2>
            <div className="info-grid">
              <div>
                <strong>Координаты:</strong>{" "}
                {result.lat.toFixed(4)}, {result.lon.toFixed(4)}
              </div>
              <div>
                <strong>Окно:</strong> {result.scale_months} мес.
              </div>
              <div>
                <strong>Дата окончания периода:</strong> {result.end_date}
              </div>
              <div>
                <strong>SPI:</strong> {result.spi.toFixed(2)}
              </div>
              <div>
                <strong>Категория:</strong> {result.category}
              </div>
            </div>

            {Array.isArray(result.recommendations) &&
              result.recommendations.length > 0 && (
                <div className="advice-box">
                  <h3>Рекомендации</h3>
                  <ul>
                    {result.recommendations.map((text, idx) => (
                      <li key={idx}>{text}</li>
                    ))}
                  </ul>
                </div>
              )}
          </section>
        )}

        {/* История SPI */}
        <section className="card">
          <h2>История SPI</h2>
          {historyData.length === 0 ? (
            <p>Исторических данных нет. Выполните расчёт SPI.</p>
          ) : (
            <>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={historyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
                    <Line
                      type="monotone"
                      dataKey="spi"
                      name="SPI"
                      dot={false}
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

        {/* Прогноз SPI */}
        <section className="card">
          <h2>Прогноз SPI</h2>
          {!forecast ? (
            <p>Нажмите «Получить прогноз SPI», чтобы увидеть ожидаемую динамику.</p>
          ) : forecast.forecast.length === 0 ? (
            <p>Прогнозных данных нет для заданных параметров.</p>
          ) : (
            <>
              <div className="info-grid">
                <div>
                  <strong>Текущий SPI:</strong>{" "}
                  {forecast.latest_spi.toFixed(2)} ({forecast.latest_category})
                </div>
                <div>
                  <strong>Горизонт прогноза:</strong>{" "}
                  {forecast.forecast_days} дней
                </div>
              </div>

              <div className="chart-container">
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={forecastData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
                    <Line
                      type="monotone"
                      dataKey="spi"
                      name="SPI (прогноз)"
                      dot={true}
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

              {/* Можно отдельно показать рекомендации по ближайшему дню прогноза */}
              {forecast.forecast[0]?.recommendations &&
                forecast.forecast[0].recommendations.length > 0 && (
                  <div className="advice-box">
                    <h3>Рекомендации на ближайший день</h3>
                    <ul>
                      {forecast.forecast[0].recommendations.map((text, idx) => (
                        <li key={idx}>{text}</li>
                      ))}
                    </ul>
                  </div>
                )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
