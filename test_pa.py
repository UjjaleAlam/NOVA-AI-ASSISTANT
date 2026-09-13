import core.predictive_ai as pa
import time
import math
import numpy as np
from datetime import datetime

print('=== PREDICTIVE AI AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(pa.pa_debug())

# 2. Add time series data
print()
print('2. Adding time series data...')
now = time.time()
# Generate synthetic data with trend + seasonality + noise
np.random.seed(42)
n = 200
trend = [0.1 * i for i in range(n)]
seasonal = [10 * math.sin(2 * math.pi * i / 24) for i in range(n)]
noise = [np.random.normal(0, 2) for _ in range(n)]
values = [100 + trend[i] + seasonal[i] + noise[i] for i in range(n)]
timestamps = [now - (n - i) * 3600 for i in range(n)]

data = list(zip(timestamps, values))
count = pa.add_time_series_batch('sensor_1', data)
print(f'   Added {count} data points')

# 3. Linear forecast
print()
print('3. Linear forecast...')
forecast = pa.linear_forecast('sensor_1', horizon=24)
print(f'   Model: {forecast["model_id"]}')
print(f'   Horizon: {forecast["horizon"]}')
print(f'   RMSE: {forecast["metrics"]["rmse"]:.2f}')
print(f'   Next 3 predictions:')
for p in forecast["predictions"][:3]:
    print(f'     t={p["timestamp"]:.0f}: {p["value"]:.1f} [{p["lower_ci"]:.1f}, {p["upper_ci"]:.1f}]')

# 4. Seasonal forecast
print()
print('4. Seasonal forecast...')
seasonal_fc = pa.seasonal_forecast('sensor_1', horizon=24, season_length=24)
print(f'   Model: {seasonal_fc["model_id"]}')
print(f'   Season length: {seasonal_fc["season_length"]}')
for p in seasonal_fc["predictions"][:3]:
    print(f'     t={p["timestamp"]:.0f}: {p["value"]:.1f} [{p["lower_ci"]:.1f}, {p["upper_ci"]:.1f}]')

# 5. Trend detection
print()
print('5. Trend detection...')
trend = pa.detect_trend('sensor_1', window=50)
print(f'   Direction: {trend["direction"]}')
print(f'   Slope: {trend["slope"]:.4f}')
print(f'   R²: {trend["r_squared"]:.4f}')
print(f'   Strength: {trend["strength"]:.3f}')

# 6. Seasonality detection
print()
print('6. Seasonality detection...')
season = pa.detect_seasonality('sensor_1')
print(f'   Seasonal: {season["seasonal"]}')
print(f'   Season length: {season.get("season_length", "N/A")}')
if "seasonal_indices" in season:
    print(f'   Indices (first 6): {season["seasonal_indices"][:6]}')

# 7. Trend detection on different windows
print()
print('7. Multi-window trends...')
for w in [24, 72, 168]:
    t = pa.detect_trend('sensor_1', window=w)
    print(f'   Window {w}h: {t["direction"]} (slope={t["slope"]:.4f}, R²={t["r_squared"]:.3f})')

# 8. Anomaly detection - Z-score
print()
print('8. Z-score anomaly detection...')
pa.detect_anomalies_zscore('sensor_1', threshold=2.5)
anomalies = pa.get_anomalies('sensor_1')
print(f'   Found {len(anomalies)} anomalies')
for a in anomalies[:5]:
    dt = datetime.fromtimestamp(a['timestamp']).strftime('%H:%M')
    print(f'   {dt}: value={a["value"]:.1f}, expected={a["expected"]:.1f}, score={a["score"]:.2f}')

# 9. Anomaly detection - IQR
print()
print('9. IQR anomaly detection...')
pa.detect_anomalies_iqr('sensor_1', multiplier=1.5)
anomalies2 = pa.get_anomalies('sensor_1')
print(f'   Found {len(anomalies2)} anomalies')

# 10. Regime change detection
print()
print('10. Regime change detection...')
changes = pa.detect_regime_changes('sensor_1', window=50)
print(f'   Detected {len(changes)} regime changes')
for c in changes[:3]:
    dt = datetime.fromtimestamp(c['timestamp']).strftime('%H:%M')
    print(f'   t={dt}: magnitude={c["magnitude"]:.2f}')

# 11. Seasonality detection
print()
print('11. Seasonality detection...')
season_result = pa.detect_seasonality('sensor_1')
print(f'   Seasonal: {season_result["seasonal"]}')
if season_result["seasonal"]:
    print(f'   Period: {season_result["season_length"]}')
    print(f'   Strength: {season_result["strength"]}')

# 12. Model management
print()
print('11. Model management...')
model_id = pa.create_forecast_model('Test Model', 'sensor_1', 'custom',
                                   {'param1': 1.0}, [1,2,3,4,5])
print(f'   Created model: {model_id}')
model = pa.get_forecast_model(model_id)
print(f'   Model: {model["name"]}, type: {model["model_type"]}')

models = pa.list_forecast_models('sensor_1')
print(f'   Models for sensor_1: {len(models)}')

# 13. Evaluation
print()
print('12. Model evaluation...')
eval_result = pa.evaluate_forecast_model(model_id, [6,7,8,9,10], 
                                        [time.time()+i*3600 for i in range(5)])
print(f'   RMSE: {eval_result["rmse"]:.2f}')
print(f'   MAE: {eval_result["mae"]:.2f}')
print(f'   MAPE: {eval_result["mape"]:.2f}%')

# 13. Anomaly queries
print()
print('13. Anomaly queries...')
all_anomalies = pa.get_anomalies()
print(f'   Total anomalies: {len(all_anomalies)}')

# 14. Debug
print()
print('13. Final debug:')
print(pa.pa_debug())

print()
print('=== ALL TESTS PASSED ===')