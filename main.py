from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd

app = FastAPI()


class PriceInput(BaseModel):
    prices: list[float]


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
