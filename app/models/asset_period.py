
from dataclasses import dataclass
import pandas as pd


@dataclass
class AssetPeriod():
    """Asset period"""
    points: int
    total_days: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp

    @classmethod
    def from_date_index(cls, date_index: pd.DatetimeIndex):
        """Create an AssetPeriod from a date index"""
        if date_index.empty:
            raise ValueError("Date index is empty")

        return cls(
            points=len(date_index),
            total_days=(date_index[-1] - date_index[0]).days + 1,
            start_date=date_index[0],
            end_date=date_index[-1]
        )

    @property
    def years(self):
        """Returns the number of years"""
        return self.total_days / 365.25

    @property
    def points_per_day(self):
        """Returns the number of points per day"""
        return self.points / self.total_days

    @property
    def points_per_week(self):
        """Returns the number of points per week"""
        return self.points_per_day * 7

    @property
    def points_per_month(self):
        """Returns the number of points per month"""
        return self.points_per_day * 365.25 / 12

    @property
    def points_per_year(self):
        """Returns the number of points per year"""
        return self.points_per_day * 365.25
