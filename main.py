import pandas as pd
import yfinance as yf
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class PriceInput(BaseModel):
    prices: list[float]


class TickerInput(BaseModel):
    ticker: str


@app.post("/risk_metrics")
def calculate_risk(data: PriceInput):
    prices = pd.Series(data.prices)

    if len(prices) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 prices are required")

    returns = prices.pct_change().dropna()
    volatility = returns.std()
    sharpe_ratio = returns.mean() / volatility

    drawdown = (prices / prices.cummax())-1
    max_drawdown = drawdown.min()

    return {
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown
    }


@app.post("/risk_metrics_from_ticker")
def risk_from_ticker(input: TickerInput):
    ticker = input.ticker.upper()
    try:
        df = yf.download(ticker, period="6mo")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if df.empty:
        raise HTTPException(
            status_code=404, detail="No data found for this ticker")

    prices = df["Close"].dropna()

    if len(prices) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 prices are required")

    returns = prices.pct_change().dropna()
    mean_return = returns.mean()
    volatility = returns.std()
    sharpe_ratio = mean_return / volatility

    drawdown = (prices / prices.cummax())-1
    max_drawdown = drawdown.min()

    return {
        "ticker": ticker,
        "mean_return": round(mean_return, 4),
        "volatility": round(volatility, 4),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 4)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
