# pyright: reportAttributeAccessIssue=false
from AlgorithmImports import *
import math
from RegimeAdvisor import RegimeAdvisor
import TradeCore as TC  # plain-function helpers (composition)

class SwingMVP_Deterministic_Exact(QCAlgorithm):
    START = (2024, 1, 1)
    END   = (2024, 12, 1)

    MIN_PRICE = 5.0
    LIQ_MIN_DOLLAR = 20_000_000
    UNIVERSE_TOP_N = 700

    EMA_LEN = 50
    ATR_LEN = 14
    VOL_WIN = 20
    LOOKBACK_RS = 5
    PIVOT_LOOKBACK = 20
    CAP_LOOKBACK = 60

    # Baseline knobs (RegimeAdvisor overwrites daily)
    MIN_RR = 1.8
    ENTRY_BUF_PCT = 0.001
    STOP_ATR_BASE = 1.0
    TARGET_ATR_MULT = MIN_RR
    ENTRY_SWEET_ATR = 0.25
    ENTRY_HARD_ATR  = 0.50

    BIG_DAY_PCT = 3.0
    BIG_GAP_PCT = 2.0
    VOL_MULT = 1.3

    RISK_PCT = 0.5
    MIN_EFF_RR = 1.5
    WEEK_CAP_ATR = 2.5
    GAP_SKIP_ATR = 0.40

    MAX_LONGS  = 30
    MAX_SHORTS = 30
    MAX_POS_PCT = 0.08  # 8% notional cap

    def Initialize(self):
        self.SetStartDate(*self.START)
        self.SetEndDate(*self.END)
        self.SetCash(1_000_000)

        self.UniverseSettings.Resolution = Resolution.DAILY
        self.AddUniverse(self.Coarse, self.Fine)

        self.spy = self.AddEquity("SPY", Resolution.DAILY).Symbol
        self.sector_etfs = {
            MorningstarSectorCode.BASIC_MATERIALS: "XLB",
            MorningstarSectorCode.CONSUMER_CYCLICAL: "XLY",
            MorningstarSectorCode.FINANCIAL_SERVICES: "XLF",
            MorningstarSectorCode.REAL_ESTATE: "XLRE",
            MorningstarSectorCode.CONSUMER_DEFENSIVE: "XLP",
            MorningstarSectorCode.HEALTHCARE: "XLV",
            MorningstarSectorCode.ENERGY: "XLE",
            MorningstarSectorCode.INDUSTRIALS: "XLI",
            MorningstarSectorCode.TECHNOLOGY: "XLK",
            MorningstarSectorCode.COMMUNICATION_SERVICES: "XLC",
            MorningstarSectorCode.UTILITIES: "XLU"
        }

        # Regime state (updated daily)
        self.regime = RegimeAdvisor(self, self.spy, self.sector_etfs)
        self.allow_longs = True
        self.allow_shorts = True
        self.stop_atr_mult = {"long": self.STOP_ATR_BASE, "short": self.STOP_ATR_BASE}
        self.min_rr_by_side = {"long": self.MIN_EFF_RR, "short": self.MIN_EFF_RR}
        self.week_cap_by_side = {"long": self.WEEK_CAP_ATR, "short": self.WEEK_CAP_ATR}
        self.breakout_bias = 0.0
        self.short_bias_penalty = 0.0
        self.selloff_flag = False

        self.etf_symbols = {}
        self.symdata = {}
        self.plan_by_sym = {}
        self.entry_id = {}
        self.exit_ids = {}
        self.filled_on = {}

        # Bind TradeCore helpers to self (composition, no multiple inheritance)
        self._bind_tradecore_helpers()

        self.Schedule.On(self.DateRules.EveryDay("SPY"),
                         self.TimeRules.BeforeMarketClose("SPY", 1),
                         self.ComputeEODAndPlans)
        self.Schedule.On(self.DateRules.EveryDay("SPY"),
                         self.TimeRules.AfterMarketOpen("SPY", 2),
                         self.PlaceEntries)
        self.Schedule.On(self.DateRules.EveryDay("SPY"),
                         self.TimeRules.AfterMarketOpen("SPY", 5),
                         self.EnforceWeekTimeStops)

        warm = max(self.EMA_LEN, self.ATR_LEN + 1, self.CAP_LOOKBACK + 1, self.VOL_WIN + 1, self.LOOKBACK_RS + 6)
        self.SetWarmUp(warm, Resolution.DAILY)

    # ---- helper binder ----
    def _bind_tradecore_helpers(self):
        self._avg_vol_from_bars          = lambda bw, n: TC.avg_vol_from_bars(self, bw, n)
        self._chg5d_pct                  = lambda sym:   TC.chg5d_pct(self, sym)
        self._compression_norm           = lambda s,a:   TC.compression_norm(self, s, a)
        self._entry_prox_norm_from_beyond= lambda b:     TC.entry_prox_norm_from_beyond(self, b)
        self._overext_penalty_from_beyond= lambda b:     TC.overext_penalty_from_beyond(self, b)
        self._rr_capped_long             = lambda c,a,ph,pl,ch: TC.rr_capped_long(self, c,a,ph,pl,ch)
        self._rr_capped_short            = lambda c,a,ph,pl,cl: TC.rr_capped_short(self, c,a,ph,pl,cl)
        self._dir_align                  = lambda tr,rs,cd:     TC.dir_align(self, tr, rs, cd)
        self._side_calc                  = lambda j:            TC.side_calc(self, j)
        self._watchlist_score_row        = lambda j:            TC.watchlist_score_row(self, j)
        self._infer_setup                = lambda *args:        TC.infer_setup(self, *args)
        self._tradeplan_from_row         = lambda it:           TC.tradeplan_from_row(self, it)
        self._risk_qty                   = lambda e,s,sy=None:  TC.risk_qty(self, e, s, sy)
        self._cleanup                    = lambda sym:          TC.cleanup(self, sym)

    # ---------- Universe ----------
    def Coarse(self, coarse):
        picks = [c for c in coarse
                 if c.HasFundamentalData
                 and c.Price is not None and c.Price >= self.MIN_PRICE
                 and c.DollarVolume is not None and c.DollarVolume >= self.LIQ_MIN_DOLLAR]
        picks.sort(key=lambda c: c.DollarVolume, reverse=True)
        return [c.Symbol for c in picks[:self.UNIVERSE_TOP_N]]

    def Fine(self, fine):
        out = []
        for f in fine:
            sym = f.Symbol
            etf_ticker = self.sector_etfs.get(f.AssetClassification.MorningstarSectorCode, "SPY")
            etf_sym = self.AddEquity(etf_ticker, Resolution.DAILY).Symbol if etf_ticker != "SPY" else self.spy
            self.etf_symbols[sym] = etf_sym
            out.append(sym)
        return out

    def OnSecuritiesChanged(self, changes):
        for sec in changes.AddedSecurities:
            sym = sec.Symbol
            if sym in self.symdata:
                continue
            win_size = max(self.VOL_WIN, self.LOOKBACK_RS + 6)
            self.symdata[sym] = {
                "ema50": self.EMA(sym, self.EMA_LEN, Resolution.DAILY),
                "ema20": self.EMA(sym, 20, Resolution.DAILY),
                "atr":   self.ATR(sym, self.ATR_LEN, MovingAverageType.Wilders, Resolution.DAILY),
                "maxH":  self.MAX(sym, self.PIVOT_LOOKBACK, Resolution.DAILY, Field.High),
                "minL":  self.MIN(sym, self.PIVOT_LOOKBACK, Resolution.DAILY, Field.Low),
                "capH":  self.MAX(sym, self.CAP_LOOKBACK, Resolution.DAILY, Field.High),
                "capL":  self.MIN(sym, self.CAP_LOOKBACK, Resolution.DAILY, Field.Low),
                "bars_win": RollingWindow[TradeBar](win_size),
            }
            self.Consolidate(sym, Resolution.DAILY, lambda bar, s=sym: self._on_bar(s, bar))

        for sec in changes.RemovedSecurities:
            sym = sec.Symbol
            self.symdata.pop(sym, None)
            self.etf_symbols.pop(sym, None)
            self._cleanup(sym)

    def _on_bar(self, sym, bar: TradeBar):
        sd = self.symdata.get(sym)
        if sd:
            sd["bars_win"].Add(bar)

    # ---------- Risk/holding maintenance ----------
    def EnforceWeekTimeStops(self):
        for kv in self.Portfolio:
            p = kv.Value
            if not p.Invested:
                continue
            sym = kv.Key
            if sym not in self.filled_on:
                self.filled_on[sym] = self.Time
        for kv in self.Portfolio:
            p = kv.Value
            if not p.Invested:
                continue
            sym = kv.Key
            dt = self.filled_on.get(sym)
            if not dt:
                continue
            if (self.Time - dt).days >= 7:
                ids = self.exit_ids.get(sym, {})
                try:
                    if ids.get("tp"):
                        self.Transactions.CancelOrder(ids["tp"])
                    if ids.get("sl"):
                        self.Transactions.CancelOrder(ids["sl"])
                except Exception:
                    pass
                self.Liquidate(sym, tag="WEEK_TIMESTOP")
                self._cleanup(sym)

    # ---------- Daily compute ----------
    def ComputeEODAndPlans(self):
        if self.IsWarmingUp:
            return

        # Refresh regime knobs
        try:
            r = self.regime.compute()
            k = self.regime.get_knobs() or {}
            self.allow_longs  = bool(k.get("allow_longs", True))
            self.allow_shorts = bool(k.get("allow_shorts", True))
            self.RISK_PCT     = float(k.get("risk_pct", self.RISK_PCT))
            self.stop_atr_mult = {
                "long": float(k.get("stop_atr_mult", {}).get("long", self.STOP_ATR_BASE)),
                "short": float(k.get("stop_atr_mult", {}).get("short", self.STOP_ATR_BASE))
            }
            self.min_rr_by_side = {
                "long": float(k.get("min_eff_rr", {}).get("long", self.MIN_EFF_RR)),
                "short": float(k.get("min_eff_rr", {}).get("short", self.MIN_EFF_RR))
            }
            self.week_cap_by_side = {
                "long": float(k.get("week_cap_atr", {}).get("long", self.WEEK_CAP_ATR)),
                "short": float(k.get("week_cap_atr", {}).get("short", self.WEEK_CAP_ATR))
            }
            self.GAP_SKIP_ATR = float(k.get("gap_skip_atr", self.GAP_SKIP_ATR))
            self.VOL_MULT     = float(k.get("vol_mult", self.VOL_MULT))
            self.BIG_DAY_PCT  = float(k.get("big_day_pct", self.BIG_DAY_PCT))
            self.BIG_GAP_PCT  = float(k.get("big_gap_pct", self.BIG_GAP_PCT))
            self.breakout_bias = float(k.get("breakout_bias", 0.0))
            self.short_bias_penalty = float(k.get("short_bias_penalty", 0.0))
            self.selloff_flag = bool(k.get("selloff", False))
            if r is not None:
                self.Debug(self.regime.summary())
        except Exception as e:
            self.Debug(f"Regime compute/apply failed: {e}")

        self.EnforceWeekTimeStops()

        ctxs = []
        etf_5d_cache = {}
        for sym in set(self.etf_symbols.values()):
            etf_5d_cache[sym] = self._chg5d_pct(sym)

        for sym, sd in self.symdata.items():
            if not all([sd["ema50"].IsReady, sd["atr"].IsReady, sd["maxH"].IsReady, sd["minL"].IsReady, sd["capH"].IsReady, sd["capL"].IsReady]):
                continue
            if sym not in self.Securities:
                continue
            sec = self.Securities[sym]
            if not sec or not sec.HasData:
                continue

            bw = sd["bars_win"]
            if bw.Count < 2:
                continue

            price = float(sec.Close)
            vol = float(bw[0].Volume)
            avg20 = self._avg_vol_from_bars(bw, self.VOL_WIN)
            dollar_vol = price * avg20 if avg20 > 0 else 0.0
            ema50 = float(sd["ema50"].Current.Value)
            ema20 = float(sd["ema20"].Current.Value) if sd["ema20"].IsReady else float('nan')
            atr = float(sd["atr"].Current.Value)
            rh = float(sd["maxH"].Current.Value)
            rl = float(sd["minL"].Current.Value)
            capH = float(sd["capH"].Current.Value)
            capL = float(sd["capL"].Current.Value)
            trend_ratio = (price/ema50) if ema50 > 0 else 1.0
            chg5 = self._chg5d_pct(sym)
            etf = self.etf_symbols.get(sym, self.spy)
            etf5 = etf_5d_cache.get(etf, None)
            rs5 = (chg5 - etf5) if (chg5 is not None and etf5 is not None) else 0.0

            vol_spike = (avg20 > 0) and (vol >= avg20 * self.VOL_MULT)
            trend_up  = (ema50 > 0) and (price >= ema50)
            trend_dn  = (ema50 > 0) and (price <= ema50)
            rs_pos = (rs5 is not None) and (rs5 > 0)
            rs_neg = (rs5 is not None) and (rs5 < 0)
            liq_ok = dollar_vol >= self.LIQ_MIN_DOLLAR

            passes_long  = bool(vol_spike and trend_up and rs_pos and liq_ok)
            passes_short = bool(vol_spike and trend_dn and rs_neg and liq_ok)

            rrL = self._rr_capped_long(price, atr, rh, rl, capH)
            rrS = self._rr_capped_short(price, atr, rh, rl, capL)
            longBetter = rrL["rr_capped"] >= rrS["rr_capped"]
            rrBest = rrL if longBetter else rrS

            rrNorm = self._clamp01(0.5 + 0.5 * math.tanh((rrBest["rr_capped"] - self.MIN_RR)/0.5))

            if longBetter:
                beyond = (price - (rrL["entry"] or price)) / (atr or 1.0)
            else:
                beyond = ((rrS["entry"] or price) - price) / (atr or 1.0)
            entryProx = self._entry_prox_norm_from_beyond(beyond)

            comp = self._compression_norm(sym, atr)

            prevC = float(bw[1].Close)
            day_pct = ((price - prevC)/prevC * 100.0) if prevC else 0.0
            today_open = float(bw[0].Open)
            gap_pct = ((today_open - prevC)/prevC * 100.0) if prevC else 0.0
            big_day_pen = self._clamp01((abs(day_pct) - self.BIG_DAY_PCT)/self.BIG_DAY_PCT)
            gap_pen     = self._clamp01((abs(gap_pct) - self.BIG_GAP_PCT)/self.BIG_GAP_PCT)
            overext_pen = self._overext_penalty_from_beyond(beyond)

            ctxs.append({
                "symbol": sym, "ticker": sym.Value, "scan_date": self.Time.date().isoformat(),
                "close": price, "volume": vol, "avg_vol_20": avg20, "dollar_vol_avg20": dollar_vol,
                "ema_50": ema50, "ema_20": ema20,
                "atr14": atr, "recent_high": rh, "recent_low": rl, "cap_high_60": capH, "cap_low_60": capL,
                "chg_5d_pct": chg5, "sector_chg_5d_pct": etf5, "rs_sector_5d": rs5,
                "vol_ratio": (vol/avg20) if avg20>0 else 0.0, "trend_ratio": trend_ratio,
                "passes_all_long": passes_long, "passes_all_short": passes_short,
                "rr_long": rrL["rr_capped"], "rr_short": rrS["rr_capped"], "rr_best": rrBest["rr_capped"],
                "entry_est": rrBest["entry"], "stop_est": rrBest["stop"], "target_est": rrBest["target"],
                "rr_norm": rrNorm, "entry_prox_norm": entryProx, "compression_norm": comp,
                "big_day_penalty": round(big_day_pen,2), "gap_penalty": round(gap_pen,2), "overext_penalty": round(overext_pen,2),
                "dir_align": self._dir_align(trend_ratio, rs5, 1 if longBetter else -1),
                "short_bias_used": (0 if longBetter else 1)
            })

        for c in ctxs:
            side, conf, votes, why = self._side_calc(c)
            c["side"] = side
            c["side_confidence"] = conf
            c["side_votes"] = votes
            c["side_rationale"] = why

        scored = []
        for c in ctxs:
            row = self._watchlist_score_row(c)
            if row:
                scored.append(row)

        scored.sort(key=lambda r: (-(r.get("rr_best") or 0),
                                   -r["_tb"]["score"],
                                   -r["_tb"]["rs_5d"],
                                   -r["_tb"]["vol_ratio"],
                                   -(r["_tb"]["dollar_vol"] or 0)))

        self.plan_by_sym.clear()
        for r in scored:
            p = self._tradeplan_from_row(r)
            if not p:
                continue
            if p["status"] in ("ok", "ok_partial"):
                sym = p.get("symbol") if isinstance(p.get("symbol"), Symbol) else None
                qty = self._risk_qty(p["entry"], p["stop"], sym)
                if qty > 0 and sym is not None:
                    p["qty"] = qty
                    self.plan_by_sym[sym] = p

    # ---------- Orders ----------
    def PlaceEntries(self):
        if not self.plan_by_sym:
            return

        invested_longs  = sum(1 for kv in self.Portfolio if kv.Value.Invested and kv.Value.Quantity > 0)
        invested_shorts = sum(1 for kv in self.Portfolio if kv.Value.Invested and kv.Value.Quantity < 0)
        long_slots  = max(0, self.MAX_LONGS  - invested_longs)
        short_slots = max(0, self.MAX_SHORTS - invested_shorts)
        if long_slots + short_slots == 0:
            return

        items = list(self.plan_by_sym.items())
        items.sort(key=lambda kv: -(kv[1].get("score") or 0))

        for sym, p in items:
            if (sym not in self.Securities) or (sym not in self.symdata):
                self._cleanup(sym)
                self.plan_by_sym.pop(sym, None)
                continue

            # Regime gating
            if p["side"] == "long" and not self.allow_longs:
                continue
            if p["side"] == "short" and not self.allow_shorts:
                continue

            sec = self.Securities[sym]
            sd  = self.symdata[sym]
            if not sec.HasData or not sd["atr"].IsReady:
                continue
            if sym in self.entry_id or self.Portfolio[sym].Invested:
                continue
            if p["side"] == "long" and long_slots <= 0:
                continue
            if p["side"] == "short" and short_slots <= 0:
                continue

            atr = float(sd["atr"].Current.Value)
            o = float(sec.Open)
            if p["side"] == "long"  and o > p["entry"] + self.GAP_SKIP_ATR*atr:
                continue
            if p["side"] == "short" and o < p["entry"] - self.GAP_SKIP_ATR*atr:
                continue

            oid = self.StopMarketOrder(
                sym,
                p["qty"] if p["side"]=="long" else -p["qty"],
                p["entry"],
                tag=f"ENTRY {p['side'][0].upper()} {p['entry']:.2f}|SL {p['stop']:.2f}|TP {p['t2']:.2f}"
            )
            self.entry_id[sym] = oid
            if p["side"]=="long":
                long_slots -= 1
            else:
                short_slots -= 1

    def OnOrderEvent(self, oe: OrderEvent):
        if oe.Status not in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            return
        sym = self.Transactions.GetOrderById(oe.OrderId).Symbol

        if sym in self.entry_id and oe.OrderId == self.entry_id[sym] and oe.Status == OrderStatus.FILLED:
            p = self.plan_by_sym.get(sym)
            if not p:
                return
            self.filled_on[sym] = self.Time
            q = int(p["qty"])
            if p["side"]=="long":
                tp_id = self.LimitOrder(sym, -q, p["t2"], tag=f"TP {p['t2']:.2f}")
                sl_id = self.StopMarketOrder(sym, -q, p["stop"], tag=f"SL {p['stop']:.2f}")
            else:
                tp_id = self.LimitOrder(sym,  q, p["t2"], tag=f"TP {p['t2']:.2f}")
                sl_id = self.StopMarketOrder(sym,  q, p["stop"], tag=f"SL {p['stop']:.2f}")
            self.exit_ids[sym] = {"tp": tp_id, "sl": sl_id}
            return

        if sym in self.exit_ids:
            ids = self.exit_ids[sym]
            if oe.OrderId == ids.get("tp") and oe.Status == OrderStatus.FILLED:
                if ids.get("sl"):
                    self.Transactions.CancelOrder(ids["sl"])
                self._cleanup(sym)
            elif oe.OrderId == ids.get("sl") and oe.Status == OrderStatus.FILLED:
                if ids.get("tp"):
                    self.Transactions.CancelOrder(ids["tp"])
                self._cleanup(sym)

    @staticmethod
    def _clamp01(x):
        return 0.0 if x < 0 else 1.0 if x > 1 else x
