import numpy as np


def get_fitted_values(values: list[float]) -> np.ndarray:
    """ Get fitted values for a list of values using exponential trend. """
    x = np.arange(len(values))
    y_log = np.log(values)
    z_exp = np.polyfit(x, y_log, 1)
    p_exp = np.poly1d(z_exp)
    y_exp = np.exp(p_exp(x))
    return y_exp, p_exp
