import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

function App() {
  const [stats, setStats] = useState(null);
  const [anomalyData, setAnomalyData] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboardData() {
    try {
      setLoading(true);
      setError("");

      const recentResponse = await fetch(`${API_BASE_URL}/transactions/recent`);
      const recentData = await recentResponse.json();

      const statsResponse = await fetch(`${API_BASE_URL}/transactions/stats`);
      const statsData = await statsResponse.json();

      const anomalyResponse = await fetch(`${API_BASE_URL}/transactions/anomalies`);
      const anomalyResult = await anomalyResponse.json();

      setRecentTransactions(recentData);
      setStats(statsData);
      setAnomalyData(anomalyResult);
    } catch (err) {
      setError("Failed to load Bitcoin transaction data.");
    } finally {
      setLoading(false);
    }
  }

useEffect(() => {
  loadDashboardData();

  const intervalId = setInterval(() => {
    loadDashboardData();
  }, 10000);

  return () => clearInterval(intervalId);
}, []);

  const chartData = recentTransactions.map((transaction, index) => ({
    index: index + 1,
    fee_rate: transaction.fee_rate,
  }));


  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Bitcoin realtime monitoring</p>
          <h1>Bitcoin Transaction Anomaly Dashboard</h1>
        </div>

        <button onClick={loadDashboardData}>Refresh</button>
      </header>

      {loading && <p>Loading Bitcoin transaction data...</p>}
      {error && <p className="error">{error}</p>}

      {stats && (
        <section className="stats-grid">
          <div className="stat-card">
            <span>Total transactions</span>
            <strong>{stats.total_transactions}</strong>
          </div>

          <div className="stat-card">
            <span>Average fee rate</span>
            <strong>{stats.average_fee_rate} sat/vB</strong>
          </div>

          <div className="stat-card">
            <span>Max fee rate</span>
            <strong>{stats.max_fee_rate} sat/vB</strong>
          </div>

          <div className="stat-card">
            <span>Average value</span>
            <strong>{stats.average_value} sats</strong>
          </div>
        </section>
      )}
      {chartData.length > 0 && (
        <section className="chart-section">
          <h2>Recent Transactions Fee Rate</h2>

          <div className="chart-card">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="index"
                  label={{
                    value: "Transaction order",
                    position: "insideBottom",
                    offset: -5,
                  }}
                />
                <YAxis
                  label={{
                    value: "Fee rate sat/vB",
                    angle: -90,
                    position: "insideLeft",
                  }}
                />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="fee_rate"
                  stroke="#0f766e"
                  strokeWidth={3}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}




      {anomalyData && (
        <section>
          <h2>Anomalies</h2>
          <p>
            Method: {anomalyData.method}. Analysed{" "}
            {anomalyData.total_transactions_analysed} transactions. Anomaly score
            threshold: {anomalyData.score_threshold}.
          </p>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>TXID</th>
                  <th>Fee</th>
                  <th>Vsize</th>
                  <th>Fee rate</th>
                  <th>Value</th>
                  <th>Reason</th>
                </tr>
              </thead>

              <tbody>
                {anomalyData.anomalies.map((transaction) => (
                  <tr key={transaction.txid} className="anomaly-row">
                    <td>{transaction.txid.slice(0, 16)}...</td>
                    <td>{transaction.fee}</td>
                    <td>{transaction.vsize}</td>
                    <td>{transaction.fee_rate}</td>
                    <td>{transaction.value}</td>
                    <td>{transaction.anomaly_reasons.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2>Recent Transactions</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>TXID</th>
                <th>Fee</th>
                <th>Vsize</th>
                <th>Fee rate</th>
                <th>Value</th>
              </tr>
            </thead>

            <tbody>
              {recentTransactions.map((transaction) => (
                <tr key={transaction.txid}>
                  <td>{transaction.txid.slice(0, 16)}...</td>
                  <td>{transaction.fee}</td>
                  <td>{transaction.vsize}</td>
                  <td>{transaction.fee_rate}</td>
                  <td>{transaction.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

export default App;