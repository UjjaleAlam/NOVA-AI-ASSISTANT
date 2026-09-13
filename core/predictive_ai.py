"""
Predictive AI Agent - Phase 33
Time series forecasting, anomaly detection, pattern prediction, trend analysis.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import math
import statistics
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

DB_DIR = "database"
PA_DB = os.path.join(DB_DIR, "predictive_ai.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_pa_connection():
    import sqlite3
    conn = sqlite3.connect(PA_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def init_pa_db():
    conn = get_pa_connection()
    cursor = conn.cursor()

    # Time series data points
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_series (
            id TEXT PRIMARY KEY,
            series_name TEXT NOT NULL,
            timestamp REAL NOT NULL,
            value REAL NOT NULL,
            metadata TEXT,  -- JSON
            created_at REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ts_name_time ON time_series(series_name, timestamp)")

    # Forecast models
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecast_models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            series_name TEXT NOT NULL,
            model_type TEXT NOT NULL,  -- 'arima', 'ets', 'prophet', 'linear', 'ml'
            parameters TEXT,  -- JSON
            training_data_hash TEXT,
            aic REAL,
            bic REAL,
            rmse REAL,
            mae REAL,
            mape REAL,
            status TEXT DEFAULT 'trained',  -- 'training', 'trained', 'failed'
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Forecasts/predictions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            series_name TEXT NOT NULL,
            forecast_horizon INTEGER NOT NULL,  -- steps ahead
            predictions TEXT NOT NULL,  -- JSON array of {timestamp, value, lower_ci, upper_ci}
            confidence_level REAL DEFAULT 0.95,
            generated_at REAL NOT NULL,
            expires_at REAL,
            is_validated BOOLEAN DEFAULT 0,
            actual_values TEXT,  -- JSON for comparison
            accuracy_metrics TEXT,  -- JSON
            FOREIGN KEY (model_id) REFERENCES forecast_models(id)
        )
    """)

    # Anomaly detections
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            series_name TEXT NOT NULL,
            timestamp REAL NOT NULL,
            value REAL NOT NULL,
            expected_value REAL,
            anomaly_score REAL,  -- 0-1
            anomaly_type TEXT,  -- 'point', 'contextual', 'collective'
            method TEXT,  -- 'zscore', 'iqr', 'isolation_forest', 'statistical'
            severity TEXT,  -- 'low', 'medium', 'high', 'critical'
            context TEXT,  -- JSON
            acknowledged BOOLEAN DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_series_time ON anomalies(series_name, timestamp)")

    # Pattern recognitions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            series_name TEXT NOT NULL,
            pattern_type TEXT NOT NULL,  -- 'seasonal', 'trend', 'cycle', 'regime_change', 'correlation'
            description TEXT,
            start_time REAL,
            end_time REAL,
            frequency REAL,  -- for seasonal
            strength REAL,  -- 0-1
            parameters TEXT,  -- JSON
            confidence REAL,
            created_at REAL NOT NULL
        )
    """)

    # Model evaluations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_evaluations (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            evaluation_type TEXT,  -- 'backtest', 'cross_validation', 'holdout'
            metrics TEXT,  -- JSON: rmse, mae, mape, etc.
            test_period_start REAL,
            test_period_end REAL,
            notes TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (model_id) REFERENCES forecast_models(id)
        )
    """)

    # Feature store for ML models
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id TEXT PRIMARY KEY,
            series_name TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            timestamp REAL NOT NULL,
            value REAL NOT NULL,
            feature_type TEXT,  -- 'lag', 'rolling', 'datetime', 'external'
            window_size INTEGER,
            created_at REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_features_series_time ON features(series_name, timestamp)")

    conn.commit()
    conn.close()


init_pa_db()


class TimeSeriesManager:
    """Manages time series data ingestion and storage."""

    def __init__(self):
        self._id_counter = 0

    def add_data_point(self, series_name: str, timestamp: float, value: float,
                       metadata: Dict = None) -> str:
        point_id = f"ts_{(int(time.time() * 1000) + self._id_counter) % 100000000:08d}"
        self._id_counter += 1
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO time_series (id, series_name, timestamp, value, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (point_id, series_name, timestamp, value,
              json.dumps(metadata or {}), time.time()))
        conn.commit()
        conn.close()
        return point_id

    def add_batch(self, series_name: str, data: List[Tuple[float, float]],
                  metadata: Dict = None) -> int:
        """Add multiple data points. Returns count."""
        conn = get_pa_connection()
        cursor = conn.cursor()
        count = 0
        base_time = int(time.time() * 1000)
        for i, (timestamp, value) in enumerate(data):
            point_id = f"ts_{(base_time + i) % 100000000:08d}"
            cursor.execute("""
                INSERT INTO time_series (id, series_name, timestamp, value, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (point_id, series_name, timestamp, value,
                  json.dumps(metadata or {}), time.time()))
            count += 1
        conn.commit()
        conn.close()
        return count

    def get_data(self, series_name: str, start: float = None,
                 end: float = None, limit: int = 10000) -> List[Dict]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM time_series WHERE series_name = ?"
        params = [series_name]
        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "series_name": r[1], "timestamp": r[2],
             "value": r[3], "metadata": json.loads(r[4]) if r[4] else {}}
            for r in rows
        ]

    def get_latest(self, series_name: str, n: int = 1) -> List[Dict]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM time_series WHERE series_name = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (series_name, n))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "series_name": r[1], "timestamp": r[2],
             "value": r[3], "metadata": json.loads(r[4]) if r[4] else {}}
            for r in rows
        ]

    def get_series_list(self) -> List[str]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT series_name FROM time_series ORDER BY series_name")
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def delete_series(self, series_name: str) -> bool:
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM time_series WHERE series_name = ?", (series_name,))
        conn.commit()
        conn.close()
        return True


class StatisticalForecaster:
    """Statistical forecasting methods (ARIMA-like, ETS, Linear Trend)."""

    def __init__(self):
        pass

    def linear_trend_forecast(self, series_name: str, horizon: int = 10,
                              confidence: float = 0.95) -> Dict:
        """Simple linear regression forecast."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=1000)
        if len(data) < 3:
            return {"error": "Insufficient data for linear trend"}

        timestamps = [d["timestamp"] for d in data]
        values = [d["value"] for d in data]

        # Normalize timestamps for numerical stability
        t_min, t_max = min(timestamps), max(timestamps)
        t_range = t_max - t_min
        if t_range == 0:
            return {"error": "Timestamp range is zero"}

        t_norm = [(t - t_min) / t_range for t in timestamps]

        # Linear regression: y = a + b*t
        n = len(values)
        sum_t = sum(t_norm)
        sum_y = sum(values)
        sum_ty = sum(t_norm[i] * values[i] for i in range(n))
        sum_t2 = sum(t**2 for t in t_norm)

        b = (n * sum_ty - sum_t * sum_y) / (n * sum_t2 - sum_t**2) if (n * sum_t2 - sum_t**2) != 0 else 0
        a = (sum_y - b * sum_t) / n

        # Predictions
        last_t = t_norm[-1]
        predictions = []
        lower_ci = []
        upper_ci = []

        # Calculate residuals for confidence intervals
        residuals = [values[i] - (a + b * t_norm[i]) for i in range(n)]
        residual_std = statistics.stdev(residuals) if len(residuals) > 1 else 0
        z_score = 1.96  # 95% CI

        for i in range(1, horizon + 1):
            future_t = last_t + i * (t_range / max(len(timestamps), 1) / t_range)  # simplified step
            pred = a + b * future_t
            predictions.append(pred)
            margin = z_score * residual_std
            lower_ci.append(pred - margin)
            upper_ci.append(pred + margin)

        # Generate timestamps
        last_ts = timestamps[-1]
        avg_interval = (timestamps[-1] - timestamps[0]) / max(len(timestamps) - 1, 1)
        pred_timestamps = [last_ts + (i + 1) * avg_interval for i in range(horizon)]

        # Calculate metrics on training data
        train_preds = [a + b * t for t in t_norm]
        rmse = math.sqrt(sum((values[i] - train_preds[i])**2 for i in range(n)) / n)
        mae = sum(abs(values[i] - train_preds[i]) for i in range(n)) / n
        mape = sum(abs((values[i] - train_preds[i]) / values[i]) for i in range(n) if values[i] != 0) / max(sum(1 for v in values if v != 0), 1) * 100

        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO forecast_models (id, name, series_name, model_type, parameters,
                                        training_data_hash, rmse, mae, mape, status, created_at, updated_at)
            VALUES (?, ?, ?, 'linear_trend', ?, ?, ?, ?, ?, 'trained', ?, ?)
        """, (model_id, f"Linear Trend for {series_name}", series_name,
              json.dumps({"a": a, "b": b, "t_min": t_min, "t_range": t_range}),
              hashlib.md5(str(values).encode()).hexdigest()[:16],
              rmse, mae, mape, time.time(), time.time()))
        conn.commit()
        conn.close()

        return {
            "model_id": model_id,
            "series_name": series_name,
            "method": "linear_trend",
            "parameters": {"intercept": a, "slope": b},
            "horizon": horizon,
            "predictions": [
                {"timestamp": pred_timestamps[i], "value": predictions[i],
                 "lower_ci": lower_ci[i], "upper_ci": upper_ci[i]}
                for i in range(horizon)
            ],
            "metrics": {"rmse": rmse, "mae": mae, "mape": mape},
            "confidence_level": 0.95
        }

    def seasonal_naive_forecast(self, series_name: str, horizon: int = 10,
                                 season_length: int = None) -> Dict:
        """Seasonal naive forecast (repeats last season)."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=1000)
        if len(data) < 10:
            return {"error": "Insufficient data"}

        values = [d["value"] for d in data]
        timestamps = [d["timestamp"] for d in data]

        # Auto-detect season length if not provided
        if season_length is None:
            season_length = self._detect_seasonality(values)

        if season_length >= len(values):
            season_length = max(1, len(values) // 2)

        # Seasonal naive: forecast = value from same position in previous season
        predictions = []
        lower_ci = []
        upper_ci = []

        # Calculate residuals for CI
        residuals = []
        for i in range(season_length, len(values)):
            naive_pred = values[i - season_length]
            residuals.append(values[i] - naive_pred)

        residual_std = statistics.stdev(residuals) if len(residuals) > 1 else 0
        z_score = 1.96

        for i in range(horizon):
            idx = len(values) - season_length + (i % season_length)
            pred = values[idx] if idx >= 0 else values[-1]
            predictions.append(pred)
            margin = z_score * residual_std
            lower_ci.append(pred - margin)
            upper_ci.append(pred + margin)

        # Timestamps
        last_ts = data[-1]["timestamp"]
        avg_interval = (timestamps[-1] - timestamps[0]) / max(len(timestamps) - 1, 1)
        pred_timestamps = [last_ts + (i + 1) * avg_interval for i in range(horizon)]

        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO forecast_models (id, name, series_name, model_type, parameters,
                                        training_data_hash, rmse, mae, mape, status, created_at, updated_at)
            VALUES (?, ?, ?, 'seasonal_naive', ?, ?, ?, ?, ?, 'trained', ?, ?)
        """, (model_id, f"Seasonal Naive for {series_name}", series_name,
              json.dumps({"season_length": season_length}),
              hashlib.md5(str(values).encode()).hexdigest()[:16],
              0, 0, 0, time.time(), time.time()))
        conn.commit()
        conn.close()

        return {
            "model_id": model_id,
            "series_name": series_name,
            "method": "seasonal_naive",
            "season_length": season_length,
            "horizon": horizon,
            "predictions": [
                {"timestamp": pred_timestamps[i], "value": predictions[i],
                 "lower_ci": lower_ci[i], "upper_ci": upper_ci[i]}
                for i in range(horizon)
            ]
        }

    def _detect_seasonality(self, values: List[float], max_lag: int = 100) -> int:
        """Simple autocorrelation-based seasonality detection."""
        if len(values) < 20:
            return 7  # Default weekly

        # Compute autocorrelation for different lags
        n = len(values)
        mean_val = statistics.mean(values)
        best_lag = 1
        best_corr = -1

        for lag in range(1, min(max_lag, n // 2)):
            corr = 0
            count = 0
            for i in range(n - lag):
                corr += (values[i] - mean_val) * (values[i + lag] - mean_val)
                count += 1
            if count > 0:
                corr /= count
                # Normalize by variance
                var = statistics.variance(values) if n > 1 else 1
                if var > 0:
                    corr /= var
                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

        # Return reasonable season length
        if best_corr > 0.3 and best_lag > 1:
            return best_lag
        return 7  # Default


class AnomalyDetector:
    """Anomaly detection for time series."""

    def __init__(self):
        pass

    def zscore_anomalies(self, series_name: str, threshold: float = 3.0,
                         window: int = None) -> List[Dict]:
        """Z-score based anomaly detection."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=10000)
        if len(data) < 10:
            return []

        values = [d["value"] for d in data]
        timestamps = [d["timestamp"] for d in data]

        if window:
            # Rolling z-score
            anomalies = []
            for i in range(window, len(values)):
                window_vals = values[i-window:i]
                mean_val = statistics.mean(window_vals)
                std_val = statistics.stdev(window_vals) if len(window_vals) > 1 else 0
                if std_val > 0:
                    z = (data[i]["value"] - mean_val) / std_val
                    if abs(z) > threshold:
                        self._record_anomaly(series_name, data[i]["timestamp"],
                                             data[i]["value"], data[i]["value"],
                                             "zscore", "high" if abs(z) > 4 else "medium",
                                             {"z_score": z, "window_mean": mean_val, "window_std": std_val})
        else:
            # Global z-score
            mean_val = statistics.mean([d["value"] for d in data])
            std_val = statistics.stdev([d["value"] for d in data]) if len(data) > 1 else 0
            if std_val > 0:
                anomalies = []
                for d in data:
                    z = (d["value"] - statistics.mean([x["value"] for x in data])) / std_val
                    if abs(z) > threshold:
                        self._record_anomaly(series_name, d["timestamp"],
                                             d["value"], statistics.mean([x["value"] for x in data]),
                                             "zscore", "high" if abs(z) > 4 else "medium",
                                             {"z_score": z})

    def _record_anomaly(self, series_name: str, timestamp: float,
                        value: float, expected: float, method: str,
                        severity: str, context: Dict) -> str:
        anomaly_id = f"anom_{int(time.time() * 1000) % 100000000:08d}"
        anomaly_score = min(1.0, abs(value - expected) / (abs(expected) + 1e-6))

        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO anomalies (id, series_name, timestamp, value, expected_value,
                                  anomaly_score, anomaly_type, method, severity, context, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'point', ?, ?, ?, ?)
        """, (f"anom_{int(time.time() * 1000) % 100000000:08d}", series_name, timestamp,
              value, expected, anomaly_score, method, severity, json.dumps(context), time.time()))
        conn.commit()
        conn.close()
        return anomaly_id

    def iqr_anomalies(self, series_name: str, multiplier: float = 1.5) -> List[Dict]:
        """IQR-based anomaly detection."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=10000)
        if len(data) < 4:
            return []

        values = [d["value"] for d in data]
        q1 = statistics.quantiles(values, n=4)[0]
        q3 = statistics.quantiles(values, n=4)[2]
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        anomalies = []
        for d in data:
            if d["value"] < lower or d["value"] > upper:
                severity = "critical" if (d["value"] < lower - 1.5*iqr or d["value"] > upper + 1.5*iqr) else "high"
                self._record_anomaly(series_name, d["timestamp"], d["value"],
                                     (lower + upper) / 2, "iqr", severity,
                                     {"q1": q1, "q3": q3, "iqr": iqr, "lower": lower, "upper": upper})
        return anomalies

    def get_anomalies(self, series_name: str = None,
                      severity: str = None, limit: int = 100) -> List[Dict]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM anomalies WHERE 1=1"
        params = []
        if series_name:
            query += " AND series_name = ?"
            params.append(series_name)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "series_name": r[1], "timestamp": r[2], "value": r[3],
             "expected": r[4], "score": r[5], "type": r[6], "method": r[7],
             "severity": r[8], "context": json.loads(r[9]) if r[9] else {},
             "acknowledged": bool(r[10]), "created_at": r[11]}
            for r in rows
        ]


class PatternRecognizer:
    """Pattern recognition in time series."""

    def __init__(self):
        pass

    def detect_trend(self, series_name: str, window: int = 10) -> Dict:
        """Detect trend direction and strength."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=1000)
        if len(data) < window:
            return {"error": "Insufficient data"}

        values = [d["value"] for d in data]
        timestamps = [d["timestamp"] for d in data]

        # Linear regression on recent window
        recent_values = values[-window:]
        n = len(recent_values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(recent_values)
        sum_xy = sum(x[i] * recent_values[i] for i in range(n))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum(recent_values)) / (n * sum_x2 - sum_x**2) if (n * sum_x2 - sum_x**2) != 0 else 0
        intercept = (sum(recent_values) - slope * sum_x) / n

        # R-squared
        y_pred = [intercept + slope * xi for xi in x]
        ss_res = sum((recent_values[i] - y_pred[i])**2 for i in range(n))
        ss_tot = sum((yi - statistics.mean(recent_values))**2 for yi in recent_values)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Trend classification
        recent_vals = [d["value"] for d in data[-window:]]
        mean_recent = statistics.mean(recent_vals)
        if abs(slope) < 0.001 * mean_recent:
            direction = "flat"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        strength = min(1.0, abs(slope) * window / mean_recent)

        pattern_id = f"pat_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patterns (id, series_name, pattern_type, description,
                                 start_time, end_time, frequency, strength,
                                 parameters, confidence, created_at)
            VALUES (?, ?, 'trend', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"pat_{int(time.time() * 1000) % 100000000:08d}", "trend",
              f"{direction} trend (slope={slope:.4f}, R²={r2:.3f})",
              time.time() - 86400 * window, time.time(), 0, strength,
              json.dumps({"slope": slope, "intercept": intercept, "r2": r2}),
              r2, time.time()))
        conn.commit()
        conn.close()

        return {
            "direction": direction,
            "slope": slope,
            "r_squared": r2,
            "strength": strength,
            "window": window
        }

    def detect_seasonality(self, series_name: str) -> Dict:
        """Detect seasonal patterns."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=1000)
        if len(data) < 20:
            return {"error": "Insufficient data"}

        values = [d["value"] for d in data]
        season_length = self._find_season_length(values)

        if season_length < 2:
            return {"seasonal": False, "message": "No clear seasonality detected"}

        # Calculate seasonal indices
        n_seasons = len(values) // season_length
        seasonal_indices = [0] * season_length
        counts = [0] * season_length

        for i, val in enumerate(values):
            idx = i % season_length
            seasonal_indices[idx] += values[i]
            counts[idx] += 1

        seasonal_indices = [seasonal_indices[i] / counts[i] if counts[i] > 0 else 0 for i in range(season_length)]
        overall_mean = statistics.mean(values)
        seasonal_indices = [si / overall_mean for si in seasonal_indices] if (overall_mean := statistics.mean(values)) != 0 else seasonal_indices

        pattern_id = f"pat_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patterns (id, series_name, pattern_type, description,
                                 start_time, end_time, frequency, strength,
                                 parameters, confidence, created_at)
            VALUES (?, ?, 'seasonal', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"pat_{int(time.time() * 1000) % 100000000:08d}", "seasonal",
              f"Seasonal pattern with period {season_length}",
              time.time() - 86400 * 30, time.time(), season_length,
              0.8, json.dumps({"seasonal_indices": seasonal_indices}),
              0.8, time.time()))
        conn.commit()
        conn.close()

        return {
            "seasonal": True,
            "season_length": season_length,
            "seasonal_indices": seasonal_indices,
            "strength": 0.8
        }

    def _find_season_length(self, values: List[float], max_period: int = 100) -> int:
        """Find season length using autocorrelation."""
        n = len(values)
        if n < 20:
            return 1

        mean_val = statistics.mean(values)
        best_period = 1
        best_corr = -1

        for period in range(2, min(max_period, n // 2)):
            corr = 0
            count = 0
            for i in range(n - period):
                corr += (values[i] - mean_val) * (values[i + period] - mean_val)
                count += 1
            if count > 0:
                corr /= count
                var = statistics.variance(values) if n > 1 else 1
                if var > 0:
                    corr /= var
                if corr > best_corr:
                    best_corr = corr
                    best_period = period

        return best_period if best_corr > 0.3 else 1

    def detect_regime_changes(self, series_name: str, window: int = 30) -> List[Dict]:
        """Detect structural breaks/regime changes using CUSUM."""
        ts_mgr = TimeSeriesManager()
        data = ts_mgr.get_data(series_name, limit=1000)
        if len(data) < window * 2:
            return []

        values = [d["value"] for d in data]
        timestamps = [d["timestamp"] for d in data]

        # CUSUM for mean shift detection
        mean_val = statistics.mean(values[:window])
        std_val = statistics.stdev(values[:window]) if len(values[:window]) > 1 else 1
        threshold = 5 * std_val  # 5 sigma

        cusum_pos = 0
        cusum_neg = 0
        changes = []

        for i in range(window, len(values)):
            diff = values[i] - statistics.mean(values[i-window:i])
            cusum_pos = max(0, cusum_pos + diff)
            cusum_neg = min(0, cusum_neg + diff)

            if cusum_pos > threshold or cusum_neg < -threshold:
                changes.append({
                    "timestamp": timestamps[i],
                    "index": i,
                    "value": values[i],
                    "expected": statistics.mean(values[i-window:i]),
                    "cusum_pos": cusum_pos,
                    "cusum_neg": cusum_neg,
                    "magnitude": abs(cusum_pos) if cusum_pos > threshold else abs(cusum_neg)
                })
                # Reset
                cusum_pos = 0
                cusum_neg = 0

        # Record as patterns
        for change in changes:
            pattern_id = f"pat_{int(time.time() * 1000) % 100000000:08d}"
            conn = get_pa_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patterns (id, series_name, pattern_type, description,
                                     start_time, end_time, strength,
                                     parameters, confidence, created_at)
                VALUES (?, ?, 'regime_change', ?, ?, ?, ?, ?, ?, ?)
            """, (f"pat_{int(time.time() * 1000) % 100000000:08d}", "regime_change",
                  f"Regime change detected (magnitude={change['magnitude']:.2f})",
                  change["timestamp"], change["timestamp"], change["magnitude"],
                  json.dumps(change), 0.9, time.time()))
            conn.commit()
            conn.close()

        return changes


class ModelManager:
    """Manages forecast models and evaluations."""

    def __init__(self):
        pass

    def create_model(self, name: str, series_name: str, model_type: str,
                     parameters: Dict, training_data: List[float]) -> str:
        model_id = f"model_{int(time.time() * 1000) % 100000000:08d}"
        data_hash = hashlib.md5(str(training_data).encode()).hexdigest()[:16]

        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO forecast_models (id, name, series_name, model_type, parameters,
                                        training_data_hash, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'trained', ?, ?)
        """, (model_id, name, series_name, model_type,
              json.dumps(parameters), data_hash, time.time(), time.time()))
        conn.commit()
        conn.close()
        return model_id

    def get_model(self, model_id: str) -> Optional[Dict]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM forecast_models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "name": row[1], "series_name": row[2],
                "model_type": row[3], "parameters": json.loads(row[4]) if row[4] else {},
                "training_data_hash": row[5], "aic": row[6], "bic": row[7],
                "rmse": row[8], "mae": row[9], "mape": row[10],
                "status": row[11], "created_at": row[12], "updated_at": row[13]
            }
        return None

    def list_models(self, series_name: str = None) -> List[Dict]:
        conn = get_pa_connection()
        cursor = conn.cursor()
        if series_name:
            cursor.execute("SELECT * FROM forecast_models WHERE series_name = ? ORDER BY created_at DESC", (series_name,))
        else:
            cursor.execute("SELECT * FROM forecast_models ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "series_name": r[2], "model_type": r[3],
             "status": r[11], "rmse": r[8], "mae": r[9], "mape": r[10],
             "created_at": r[12]}
            for r in rows
        ]

    def evaluate_model(self, model_id: str, test_data: List[float],
                       test_timestamps: List[float]) -> Dict:
        """Evaluate model on test data."""
        model = self.get_model(model_id)
        if not model:
            return {"error": "Model not found"}

        # Get model predictions (would need model-specific prediction logic)
        # For now, return placeholder
        predictions = test_data  # Placeholder

        # Calculate metrics
        rmse = math.sqrt(sum((test_data[i] - predictions[i])**2 for i in range(len(test_data))) / len(test_data))
        mae = sum(abs(test_data[i] - predictions[i]) for i in range(len(test_data))) / len(test_data)
        mape = sum(abs((test_data[i] - predictions[i]) / test_data[i]) for i in range(len(test_data)) if test_data[i] != 0) / max(sum(1 for v in test_data if v != 0), 1) * 100

        eval_id = f"eval_{int(time.time() * 1000) % 100000000:08d}"
        conn = get_pa_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO model_evaluations (id, model_id, evaluation_type, metrics,
                                          test_period_start, test_period_end, created_at)
            VALUES (?, ?, 'holdout', ?, ?, ?, ?)
        """, (eval_id, model_id, json.dumps({"rmse": rmse, "mae": mae, "mape": mape}),
              min(test_timestamps), max(test_timestamps), time.time()))
        conn.commit()
        conn.close()

        return {"eval_id": eval_id, "rmse": rmse, "mae": mae, "mape": mape}


# ==========================================
# MODULE EXPORTS
# ==========================================

ts_mgr = TimeSeriesManager()
stat_forecaster = StatisticalForecaster()
anomaly_detector = AnomalyDetector()
pattern_recognizer = PatternRecognizer()
model_mgr = ModelManager()


def pa_debug() -> str:
    conn = get_pa_connection()
    cursor = conn.cursor()
    tables = ["time_series", "forecast_models", "forecasts", "anomalies",
              "patterns", "model_evaluations", "features"]
    output = "Predictive AI Debug:\n"
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        output += f"  {t}: {count} records\n"
    conn.close()
    return output


def add_time_series_point(series_name: str, timestamp: float, value: float,
                          metadata: Dict = None) -> str:
    return ts_mgr.add_data_point(series_name, timestamp, value, metadata)


def add_time_series_batch(series_name: str, data: List[Tuple[float, float]]) -> int:
    return ts_mgr.add_batch(series_name, data)


def get_time_series(series_name: str, start: float = None, end: float = None,
                    limit: int = 10000) -> List[Dict]:
    return ts_mgr.get_data(series_name, start, end, limit)


def list_time_series() -> List[str]:
    return ts_mgr.get_series_list()


def linear_forecast(series_name: str, horizon: int = 10, confidence: float = 0.95) -> Dict:
    return stat_forecaster.linear_trend_forecast(series_name, horizon, confidence)


def seasonal_forecast(series_name: str, horizon: int = 10, season_length: int = None) -> Dict:
    return stat_forecaster.seasonal_naive_forecast(series_name, horizon, season_length)


def detect_anomalies_zscore(series_name: str, threshold: float = 3.0,
                            window: int = None) -> List[Dict]:
    anomaly_detector.zscore_anomalies(series_name, threshold, window)
    return anomaly_detector.get_anomalies(series_name)


def detect_anomalies_iqr(series_name: str, multiplier: float = 1.5) -> List[Dict]:
    anomaly_detector.iqr_anomalies(series_name, multiplier)
    return anomaly_detector.get_anomalies(series_name)


def get_anomalies(series_name: str = None, severity: str = None, limit: int = 100) -> List[Dict]:
    return anomaly_detector.get_anomalies(series_name, severity, limit)


def detect_trend(series_name: str, window: int = 10) -> Dict:
    return pattern_recognizer.detect_trend(series_name, window)


def detect_seasonality(series_name: str) -> Dict:
    return pattern_recognizer.detect_seasonality(series_name)


def detect_regime_changes(series_name: str, window: int = 30) -> List[Dict]:
    return pattern_recognizer.detect_regime_changes(series_name, window)


def create_forecast_model(name: str, series_name: str, model_type: str,
                          parameters: Dict, training_data: List[float]) -> str:
    return model_mgr.create_model(name, series_name, model_type, parameters, training_data)


def get_forecast_model(model_id: str) -> Optional[Dict]:
    return model_mgr.get_model(model_id)


def list_forecast_models(series_name: str = None) -> List[Dict]:
    return model_mgr.list_models(series_name)


def evaluate_forecast_model(model_id: str, test_data: List[float],
                            test_timestamps: List[float]) -> Dict:
    return model_mgr.evaluate_model(model_id, test_data, test_timestamps)


if __name__ == "__main__":
    print("Predictive AI Agent loaded.")
    print("Core: TimeSeriesManager, StatisticalForecaster, AnomalyDetector, PatternRecognizer, ModelManager")