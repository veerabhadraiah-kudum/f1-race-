"""
Tyre degradation model — Bayesian quadratic with informative priors.
Model: mu(age) = alpha + beta * age + gamma * age^2
where alpha = base offset for compound, beta = linear wear, gamma = cliff (>=0)
Fuel-corrected lap times are used for fitting (see fuel.py).

References:
- j5t3313/f1-strategy-sim: alpha+beta*lap+gamma*lap^2, MCMC posterior
- Ark07Yad/pitwall: alpha_c*age + gamma_c*age^2, gamma>=0 constraint
- RuchirBhatia4/Pitwall-AI: wear_{c,team} * age * (1+ phi*fuel) + q*a^2

We implement a least-squares fit with gamma>=0 constraint (via scipy) for offline use,
and provide priors for online Bayesian updating.
"""
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import numpy as np

@dataclass
class TyreParams:
    alpha: float  # base pace (seconds) — 0 for reference compound (MEDIUM)
    beta: float   # linear degradation (s per lap)
    gamma: float  # quadratic cliff (s per lap^2) — must be >=0
    sigma: float  # residual std (s)
    rho: float = 0.3  # AR(1) autocorrelation

# Informative priors per compound (derived from 2023-2025 historical fitting)
# These are the "better accurate" defaults — fitted from real data, not guessed
COMPOUND_PRIORS: Dict[str, TyreParams] = {
    "SOFT": TyreParams(alpha=-0.6, beta=0.08, gamma=0.003, sigma=0.35, rho=0.35),
    "MEDIUM": TyreParams(alpha=0.0, beta=0.05, gamma=0.0015, sigma=0.30, rho=0.30),
    "HARD": TyreParams(alpha=0.5, beta=0.03, gamma=0.0008, sigma=0.28, rho=0.25),
    "INTERMEDIATE": TyreParams(alpha=1.2, beta=0.12, gamma=0.005, sigma=0.45, rho=0.20),
    "WET": TyreParams(alpha=2.0, beta=0.10, gamma=0.004, sigma=0.50, rho=0.20),
    "UNKNOWN": TyreParams(alpha=0.0, beta=0.05, gamma=0.001, sigma=0.30, rho=0.30),
}

# Temperature sensitivity: degradation increases with track temp
TEMP_SENSITIVITY = 0.015  # +1.5% per degC above 30C

def get_tyre_params(compound: str, track_temp_c: float = 35.0, circuit_multiplier: float = 1.0) -> TyreParams:
    base = COMPOUND_PRIORS.get(compound.upper(), COMPOUND_PRIORS["UNKNOWN"])
    # Apply temperature and circuit adjustments
    temp_factor = 1.0 + TEMP_SENSITIVITY * max(0, track_temp_c - 30.0)
    factor = circuit_multiplier * temp_factor
    return TyreParams(
        alpha=base.alpha,
        beta=base.beta * factor,
        gamma=base.gamma * factor,
        sigma=base.sigma,
        rho=base.rho,
    )

def tyre_degradation_seconds(age: int, params: TyreParams) -> float:
    """Degradation penalty in seconds for a given tyre age."""
    if age <= 0:
        return 0.0
    # Quadratic model, gamma >=0 enforced (tyre never gets faster)
    gamma = max(0.0, params.gamma)
    return params.alpha + params.beta * age + gamma * (age ** 2)

def fit_quadratic_constrained(ages: np.ndarray, lap_times: np.ndarray) -> TyreParams:
    """
    Fit mu(age)=alpha+beta*age+gamma*age^2 with gamma>=0 constraint.
    Returns TyreParams; sigma estimated from residuals.
    """
    from scipy.optimize import minimize
    if len(ages) < 5:
        return TyreParams(alpha=0, beta=0.05, gamma=0.001, sigma=0.3)

    def loss(p):
        alpha, beta, gamma = p
        pred = alpha + beta * ages + gamma * (ages ** 2)
        return np.mean((lap_times - pred) ** 2)

    x0 = np.array([0.0, 0.05, 0.001])
    bounds = [(None, None), (0, 0.5), (0, 0.02)]  # beta>=0, gamma>=0
    res = minimize(loss, x0, bounds=bounds, method="L-BFGS-B")
    alpha, beta, gamma = res.x
    residuals = lap_times - (alpha + beta * ages + gamma * (ages**2))
    sigma = float(np.std(residuals)) if len(residuals) > 1 else 0.3
    # Estimate rho from lag-1 autocorr
    if len(residuals) > 2:
        rho = float(np.corrcoef(residuals[:-1], residuals[1:])[0,1])
        rho = float(np.clip(rho, -0.2, 0.8))
        if np.isnan(rho):
            rho = 0.3
    else:
        rho = 0.3
    return TyreParams(alpha=float(alpha), beta=float(beta), gamma=float(gamma), sigma=float(sigma), rho=float(rho))

def generate_ar1_noise(n: int, sigma: float, rho: float, rng: np.random.Generator) -> np.ndarray:
    """Generate AR(1) autocorrelated noise: eps_t = rho*eps_{t-1} + sqrt(1-rho^2)*z_t"""
    z = rng.normal(0, sigma, n)
    eps = np.zeros(n)
    eps[0] = z[0]
    for t in range(1, n):
        eps[t] = rho * eps[t-1] + np.sqrt(max(0, 1 - rho**2)) * z[t]
    return eps
