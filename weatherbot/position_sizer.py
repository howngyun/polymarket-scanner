"""
position_sizer.py — Kelly fractional sizing with hard caps.

Standard Kelly for a binary outcome at price `q` paying $1:
    edge        = p - q
    decimal odds b = (1 - q) / q
    f*          = (b·p - (1-p)) / b   (= edge / (1 - q))

We use a quarter-Kelly multiplier (Patch — risk control) plus hard caps:
- Per-trade $25 (5% of $500)
- Per-trade share of liquidity ≤ 5% (P5)
- Daily loss / portfolio caps enforced upstream by paper_ledger / runner.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizeDecision:
    usd: float                     # dollar amount to deploy on this side
    shares: float                  # implied shares = usd / entry_price
    kelly_full: float              # raw Kelly fraction (for logging)
    fraction_used: float           # what we actually applied
    capped_by: str                 # 'kelly' | 'per_trade' | 'liquidity' | 'cash'


def kelly_fraction(p: float, price: float) -> float:
    """Full Kelly fraction for a YES at `price` paying $1. Returns 0 if no edge."""
    if price <= 0.0 or price >= 1.0:
        return 0.0
    edge = p - price
    if edge <= 0.0:
        return 0.0
    return edge / (1.0 - price)


def size(
    p: float,
    entry_price: float,
    *,
    bankroll_usd: float,
    available_cash_usd: float,
    market_liquidity_usd: float,
    kelly_multiplier: float = 0.25,    # quarter Kelly
    max_per_trade_usd: float = 25.0,
    max_pct_liquidity: float = 0.05,
) -> SizeDecision:
    """Translate edge into $ sized for $500 retail bankroll."""
    f_full = kelly_fraction(p, entry_price)
    f = f_full * kelly_multiplier
    raw_usd = f * bankroll_usd

    capped_by = "kelly"
    usd = raw_usd
    if usd > max_per_trade_usd:
        usd = max_per_trade_usd
        capped_by = "per_trade"
    liq_cap = max_pct_liquidity * market_liquidity_usd
    if usd > liq_cap:
        usd = liq_cap
        capped_by = "liquidity"
    if usd > available_cash_usd:
        usd = max(0.0, available_cash_usd)
        capped_by = "cash"

    if entry_price > 0:
        shares = usd / entry_price
    else:
        shares = 0.0

    return SizeDecision(
        usd=round(usd, 2),
        shares=round(shares, 4),
        kelly_full=f_full,
        fraction_used=f if usd == raw_usd else (usd / bankroll_usd if bankroll_usd else 0.0),
        capped_by=capped_by,
    )


if __name__ == "__main__":
    # Sanity table — quarter Kelly at varying edges from a $500 bankroll.
    print("p     price  full_kelly  qK*$500  capped")
    for p, price in [(0.50, 0.10), (0.30, 0.05), (0.20, 0.05), (0.10, 0.03), (0.55, 0.50)]:
        d = size(p, price, bankroll_usd=500, available_cash_usd=500,
                 market_liquidity_usd=1000)
        print(f"  {p:.2f}  {price:.3f}  {d.kelly_full:.3f}      ${d.usd:>5.2f}    {d.capped_by}")
