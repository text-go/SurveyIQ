import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.analysis import ForecastResult

def forecast_metric(values: list, periods=3):
    if len(values) < 2:
        return values, []
    X = np.arange(len(values)).reshape(-1, 1)
    y = np.array(values)
    
    poly = PolynomialFeatures(degree=1)
    X_poly = poly.fit_transform(X)
    
    model = LinearRegression()
    model.fit(X_poly, y)
    
    X_pred = np.arange(len(values), len(values) + periods).reshape(-1, 1)
    X_pred_poly = poly.transform(X_pred)
    
    pred = model.predict(X_pred_poly)
    std_err = np.std(y - model.predict(X_poly))
    ci = [[p - 1.96 * std_err, p + 1.96 * std_err] for p in pred]
    return pred.tolist(), ci

def detect_anomalies(values: list):
    if len(values) < 4:
        return []
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    anomalies = []
    for i, v in enumerate(values):
        if v < lower or v > upper:
            severity = "high" if (v < lower - iqr or v > upper + iqr) else "medium"
            anomalies.append({"index": i, "value": v, "severity": severity})
    return anomalies

async def run_forecast(db: AsyncSession, survey_id: int, question_id: int, values: list, periods=3):
    pred, ci = forecast_metric(values, periods)
    anomalies = detect_anomalies(values)
    
    fr = ForecastResult(
        survey_id=survey_id,
        question_id=question_id,
        metric_name="metric",
        historical_values=values,
        predicted_values=pred,
        confidence_intervals=ci,
        anomalies=anomalies
    )
    db.add(fr)
    await db.commit()
    return fr
