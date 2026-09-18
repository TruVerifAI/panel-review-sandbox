# RegimeAdvisor.py
from AlgorithmImports import *
import math
from statistics import pstdev
from collections import deque  # simple, reliable rolling buffer

class RegimeAdvisor:
    """
    Daily market regime detector that returns strategy knobs.
    Regime axes:
      - Trend: bull | bear | range   (SPY vs EMA200 and 5d slope)
      - Volatility: low | med | high (SPY ATR% bucket)
      - Breadth: strong | mixed | weak (% of sectors above EMA50)
      - Dispersion: cross-sector 20d return stdev (continuous)

    Outputs:
      - regime: labels + metrics for the day
      - knobs: dict with side-specific parameters and global gates
    """

    def __init__(self, algo: QCAlgorithm, spy: Symbol, sector_etfs: dict):
        self.algo = algo
        self.spy = spy
        self.sector_syms = self._unique_etfs(sector_etfs.values(), spy)

        # Indicators
        self.spy_ema50  = algo.EMA(spy, 50,  Resolution.DAILY)
        self.spy_ema200 = algo.EMA(spy, 200, Resolution.DAILY)
        self.spy_atr14  = algo.ATR(spy, 14, MovingAverageType.Wilders, Resolution.DAILY)

        # Sector trend refs
        self.sec_ema50 = {}
        for etf in self.sector_syms:
            self.sec_ema50[etf] = algo.EMA(etf, 50, Resolution.DAILY)

        # Rolling closes for 5d slope — use a plain deque (avoids .NET generics issues)
        self.spy_closes = deque(maxlen=6)  # ~5 trading days + current
        self.algo.Consolidate(spy, Resolution.DAILY, self._on_spy_bar)

        self.regime = None
        self.knobs = None
        self.last_calc_date = None

    def _unique_etfs(self, vals, spy):
        uniq_tickers = sorted({t for t in vals if t != "SPY"})
        out = []
        for t in uniq_tickers:
            try:
                sym = self.algo.AddEquity(t, Resolution.DAILY).Symbol
                out.append(sym)
            except Exception:
                pass
        return out

    def _on_spy_bar(self, bar: TradeBar):
        try:
            self.spy_closes.append(float(bar.Close))
        except Exception:
            pass

    def _ema_slope5(self):
        # ~5-day pct slope using closes in the deque
        n = len(self.spy_closes)
        if n < 2:
            return 0.0
        c0 = float(self.spy_closes[-1])
        c5 = float(self.spy_closes[0]) if n >= 6 else float(self.spy_closes[0])  # oldest in buffer
        if c5 == 0:
            return 0.0
        return (c0 - c5) / c5

    def _pct_above(self, ema_map: dict):
        above = total = 0
        for etf, ema in ema_map.items():
            if not ema.IsReady:
                continue
            sec = self.algo.Securities.get(etf, None)
            if not sec or not sec.HasData:
                continue
            total += 1
            if float(sec.Close) > float(ema.Current.Value):
                above += 1
        return (above / total) if total > 0 else 0.0

    def _rs_spread(self):
        """Cross-sector dispersion: 20-session return stdev across sector ETFs."""
        chgs = []
        for etf in self.sec_ema50.keys():
            try:
                hist = self.algo.History(etf, 21, Resolution.DAILY)
                if hist.empty:
                    continue
                try:
                    df = hist.loc[etf] if etf in hist.index.get_level_values(0) else hist
                except Exception:
                    df = hist
                c0 = float(df.iloc[-1]["close"])
                c20 = float(df.iloc[0]["close"])
                if c20 > 0:
                    chgs.append((c0 - c20) / c20)
            except Exception:
                pass
        return pstdev(chgs) if chgs else 0.0

    def _vol_bucket(self, atrp):
        if atrp < 0.012: return "low"
        if atrp < 0.020: return "med"
        return "high"

    def _trend_bucket(self, price, ema200, ema50_slope):
        if price > ema200 and ema50_slope >= 0: return "bull"
        if price < ema200 and ema50_slope <= 0: return "bear"
        return "range"

    def _breadth_label(self, pct_above):
        if pct_above >= 0.65: return "strong"
        if pct_above <= 0.35: return "weak"
        return "mixed"

    def _is_selloff(self, trend, vol, breadth, ema50_slope, atrp):
        bearish = (trend == "bear") or (ema50_slope < 0)
        weak_br = (breadth == "weak")
        high_vol = (vol == "high") or (atrp >= 0.020)
        score = int(bearish) + int(weak_br) + int(high_vol)
        return score >= 2

    def compute(self):
        if self.last_calc_date == self.algo.Time.date() and self.regime is not None:
            return self.regime
        if not (self.spy_ema50.IsReady and self.spy_ema200.IsReady and self.spy_atr14.IsReady):
            return None

        spy_px = float(self.algo.Securities[self.spy].Close)
        ema200 = float(self.spy_ema200.Current.Value)
        atrp = float(self.spy_atr14.Current.Value) / max(spy_px, 1e-6)
        slope5 = self._ema_slope5()

        breadth_pct = self._pct_above(self.sec_ema50)
        dispersion = self._rs_spread()

        vol = self._vol_bucket(atrp)
        trend = self._trend_bucket(spy_px, ema200, slope5)
        breadth = self._breadth_label(breadth_pct)
        selloff = self._is_selloff(trend, vol, breadth, slope5, atrp)

        regime = {
            "date": self.algo.Time.date().isoformat(),
            "spy_price": spy_px,
            "atrp": atrp,
            "ema50_slope_5d": slope5,
            "trend": trend,
            "volatility": vol,
            "breadth": breadth,
            "pct_sectors_above_ema50": breadth_pct,
            "dispersion": dispersion,
            "selloff": selloff
        }
        self.regime = regime
        self.last_calc_date = self.algo.Time.date()
        self.knobs = self._map_knobs(regime)
        return regime

    def get_knobs(self):
        if self.last_calc_date != self.algo.Time.date():
            self.compute()
        # safe default if not ready
        return self.knobs or {
            "allow_longs": True,
            "allow_shorts": True,
            "risk_pct": 0.5,
            "stop_atr_mult": {"long": 1.0, "short": 1.0},
            "min_eff_rr": {"long": 1.5, "short": 1.5},
            "week_cap_atr": {"long": 2.5, "short": 2.5},
            "gap_skip_atr": 0.40,
            "breakout_bias": 0.0,
            "short_bias_penalty": 0.0,
            "big_day_pct": 3.0,
            "big_gap_pct": 2.0,
            "vol_mult": 1.3,
            "selloff": False
        }

    def _map_knobs(self, R):
        trend = R["trend"]
        vol = R["volatility"]
        breadth = R["breadth"]
        atrp = R.get("atrp", 0.015)
        slope = R.get("ema50_slope_5d", 0.0)
        disp = R.get("dispersion", 0.05)
        selloff = R.get("selloff", False)

        knobs = {
            "allow_longs": True,
            "allow_shorts": True,
            "risk_pct": 0.50,  # global
            "stop_atr_mult": {"long": 1.00, "short": 1.00},
            "min_eff_rr":   {"long": 1.50, "short": 1.50},
            "week_cap_atr": {"long": 2.50, "short": 2.50},
            "gap_skip_atr": 0.40,
            "breakout_bias": 0.0,
            "short_bias_penalty": 0.0,
            "selloff": selloff
        }

        # --- Volatility scaling (risk, stops, caps, and VOL_MULT) ---
        if vol == "low":
            knobs["risk_pct"] = 0.50
            knobs["stop_atr_mult"]["long"]  = max(0.85, knobs["stop_atr_mult"]["long"]  - 0.10)
            knobs["stop_atr_mult"]["short"] = max(0.85, knobs["stop_atr_mult"]["short"] - 0.05)
            knobs["week_cap_atr"]["long"]   = max(knobs["week_cap_atr"]["long"], 2.2)
            knobs["week_cap_atr"]["short"]  = max(knobs["week_cap_atr"]["short"], 2.3)
            knobs["vol_mult"] = 1.20
        elif vol == "high":
            knobs["risk_pct"] = 0.35
            knobs["stop_atr_mult"]["long"]  = min(1.15, knobs["stop_atr_mult"]["long"]  + 0.10)
            knobs["stop_atr_mult"]["short"] = min(1.20, knobs["stop_atr_mult"]["short"] + 0.15)
            knobs["week_cap_atr"]["long"]   = max(knobs["week_cap_atr"]["long"], 3.0)
            knobs["week_cap_atr"]["short"]  = max(knobs["week_cap_atr"]["short"], 3.2)
            knobs["vol_mult"] = 1.60
        else:
            knobs["risk_pct"] = 0.45
            knobs["vol_mult"] = 1.30

        # --- Trend/Breadth tilts ---
        if trend == "bull" and breadth in ("strong", "mixed"):
            knobs["breakout_bias"] = +0.15
            knobs["min_eff_rr"]["long"] = 1.40
            slope_boost = 0.2 if slope > 0.0 else 0.0
            vol_boost = 0.2 if atrp <= 0.015 else 0.0
            target_cap_long = 2.9 + slope_boost + vol_boost  # up to ~3.3
            knobs["week_cap_atr"]["long"] = max(knobs["week_cap_atr"]["long"], target_cap_long)
            knobs["min_eff_rr"]["short"] = max(knobs["min_eff_rr"]["short"], 1.55)
            knobs["week_cap_atr"]["short"] = max(knobs["week_cap_atr"]["short"], 2.7)
        elif trend == "bear" and breadth in ("weak", "mixed"):
            knobs["breakout_bias"] = -0.05
            knobs["min_eff_rr"]["short"] = 1.40
            knobs["week_cap_atr"]["short"] = max(knobs["week_cap_atr"]["short"], 2.8)
            knobs["min_eff_rr"]["long"] = max(knobs["min_eff_rr"]["long"], 1.60)
        else:
            knobs["breakout_bias"] = -0.10
            knobs["min_eff_rr"]["long"]  = max(knobs["min_eff_rr"]["long"],  1.60)
            knobs["min_eff_rr"]["short"] = max(knobs["min_eff_rr"]["short"], 1.60)

        # --- Selloff override ---
        if selloff:
            knobs["allow_shorts"] = True
            knobs["min_eff_rr"]["short"]   = min(knobs["min_eff_rr"]["short"], 1.35)
            knobs["week_cap_atr"]["short"] = max(knobs["week_cap_atr"]["short"], 3.2)
            knobs["stop_atr_mult"]["short"] = min(1.25, knobs["stop_atr_mult"]["short"] + 0.05)
            knobs["min_eff_rr"]["long"] = max(knobs["min_eff_rr"]["long"], 1.60)

        # --- Dispersion quality tweak ---
        if disp >= 0.08:
            knobs["min_eff_rr"]["long"]  = max(1.35, knobs["min_eff_rr"]["long"]  - 0.05)
            knobs["min_eff_rr"]["short"] = max(1.35, knobs["min_eff_rr"]["short"] - 0.05)
        elif disp <= 0.04:
            knobs["min_eff_rr"]["long"]  = min(1.85, knobs["min_eff_rr"]["long"]  + 0.05)
            knobs["min_eff_rr"]["short"] = min(1.85, knobs["min_eff_rr"]["short"] + 0.05)

        # --- Dynamic BIG_DAY_PCT / BIG_GAP_PCT by volatility ---
        if vol == "low":
            knobs["big_day_pct"] = 2.0
            knobs["big_gap_pct"] = 1.0
        elif vol == "high":
            knobs["big_day_pct"] = 4.5
            knobs["big_gap_pct"] = 3.0
        else:
            knobs["big_day_pct"] = 3.0
            knobs["big_gap_pct"] = 2.0

        # Final clamps
        knobs["risk_pct"] = float(max(0.25, min(0.70, knobs["risk_pct"])))
        for k in ("long", "short"):
            knobs["stop_atr_mult"][k] = float(max(0.80, min(1.30, knobs["stop_atr_mult"][k])))
            knobs["min_eff_rr"][k]    = float(max(1.25, min(2.00, knobs["min_eff_rr"][k])))
            knobs["week_cap_atr"][k]  = float(max(2.0,  min(3.5,  knobs["week_cap_atr"][k])))

        knobs["gap_skip_atr"] = float(max(0.20, min(0.70, knobs["gap_skip_atr"])))
        knobs["breakout_bias"] = float(max(-0.30, min(+0.30, knobs["breakout_bias"])))
        knobs["short_bias_penalty"] = float(max(-0.10, min(+0.20, knobs["short_bias_penalty"])))
        knobs["vol_mult"] = float(max(1.10, min(1.80, knobs["vol_mult"])))

        return knobs

    def summary(self):
        r = self.compute()
        k = self.get_knobs()
        if not r:
            return "Regime not ready."
        return (
            f"{r['date']} | trend={r['trend']} vol={r['volatility']} breadth={r['breadth']} "
            f"atr%={r['atrp']:.2%} pct_above50={r['pct_sectors_above_ema50']:.0%} disp={r['dispersion']:.3f} selloff={r['selloff']} | "
            f"knobs: risk={k['risk_pct']:.2f}% stopATR(L/S)={k['stop_atr_mult']['long']:.2f}/{k['stop_atr_mult']['short']:.2f} "
            f"minRR(L/S)={k['min_eff_rr']['long']:.2f}/{k['min_eff_rr']['short']:.2f} "
            f"weekCap(L/S)={k['week_cap_atr']['long']:.2f}/{k['week_cap_atr']['short']:.2f} "
            f"bigDay={k['big_day_pct']:.1f}% bigGap={k['big_gap_pct']:.1f}% volMult={k['vol_mult']:.2f}"
        )
