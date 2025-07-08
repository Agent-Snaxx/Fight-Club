# MIT License
# swapBot
# Copyright (c) 2024 Agent_Snaxx
# Email: snaxxagent@gmail.com | X: @Agent_Snaxx | GitHub: Agent-Snaxx  Repo:Fight Club #AGI BOT #agentOnly
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#READ DISCLAIMER-------------------------------------------------------------------------------------------

#This project is provided for educational and experimental purposes only.
#It is not financial advice, not an investment product, and not a commercial offering.
#Use at your own risk.

#The architecture is intended for builders, developers, and technically capable users
#who understand the risks of automated trading, smart contracts, and capital exposure.

#There are no profit guarantees.  
#No strategy is foolproof.  
#No agent is immune to failure.

#Do not deploy without testing.
#Do not trade without logging.
#Do not sleep on your own assumptions.

#You are the architect.
#This system is your tool — not your replacement.
#Assist, not automate. Observe, not override.

#USE IT- OWN IT- FORK IT- FUCK IT -WRECK IT - RESET IT - REPEAT IT


import os
import json
import uuid
import time
import atexit
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
import pandas as pd
import pandas_ta as ta
import websocket

from coinbase.rest import RESTClient
import jwt  # PyJWT for JWT generation

from dotenv import load_dotenv
from oversight import BotOversight, safe_llm_call  # <-- Only these imports!
load_dotenv()

API_KEY = os.getenv("CDP_API_KEY_NAME")
API_SECRET = os.getenv("CDP_API_KEY_PRIVATE")
if not API_KEY or not API_SECRET:
    raise RuntimeError("Set CDP_API_KEY_NAME & CDP_API_KEY_PRIVATE in .env")

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

def format_doge_amt(amt):
    """Format DOGE amount to max 4 decimals for Coinbase."""
    return f"{float(amt):.4f}"

def get_current_stats(trades):
    wins = 0
    completed = 0
    pnl_total = 0.0

    # Pair buys and sells sequentially
    for i in range(len(trades) - 1):
        t1 = trades[i]
        t2 = trades[i + 1]
        if t1['side'] == 'BUY' and t2['side'] == 'SELL':
            buy_cost = float(t1['price']) * float(t1['size'])
            sell_revenue = float(t2['price']) * float(t2['size'])
            trade_pnl = sell_revenue - buy_cost
            pnl_total += trade_pnl
            completed += 1
            if trade_pnl > 0:
                wins += 1

    win_rate = wins / completed if completed > 0 else 0.0
    return pnl_total, win_rate, completed

class DogeTrader:
    PRODUCT_ID = "DOGE-USD"
    GRANULARITY = 300  # 5-minute candles
    BB_PERIOD = 25    # Adjusted from 20
    BB_STD = 2.0      # Adjusted from 1.65
    WMA_PERIOD = 25   # Adjusted from 20
    HISTORY_LEN = 100
    FEE_RATE = Decimal('0.003')  # Adjusted from 0.005

    def __init__(self, ws_url="wss://advanced-trade-ws.coinbase.com"):
        self.rest = RESTClient(api_key=API_KEY, api_secret=API_SECRET)
        self.h = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        self.in_position = False
        self.position_amount = Decimal('0')
        self.last_buy_price = None
        self.trades = []
        self.current_wma = Decimal('0')
        self.ws_url = ws_url
        self.should_reconnect = True
        atexit.register(self.print_summary)
        self.log_file = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        self.llm_log_file = "llm_advice.log"

        import csv
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "WIN", "FL", "SL", "CL", "STRAT", "ES", "EXIT", "TF",
                "ENTRY@PRICE", "FEE", "EXIT@PRICE", "PNL", "DYN"
            ])

        self.oversight = BotOversight(initial_params={
            "BB_period": 20,
            "EMA_span": 14,
            "order_size": 1,
        })

    def log_trade(self, win, fl, sl, cl, strat, es, exit_sig, tf, entry, fee, sold, pnl, dyn):
        import csv
        row = [
            datetime.now(timezone.utc).isoformat(),
            win, fl, sl, cl, strat, es, exit_sig, tf, entry, fee, sold, pnl, dyn
        ]
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def log_llm_advice(self, advice):
        """Append LLM advice to a separate log file for full trace."""
        ts = datetime.now(timezone.utc).isoformat()
        with open(self.llm_log_file, "a") as f:
            f.write(f"\n[{ts}] LLM Advice:\n{advice}\n{'-'*40}\n")

    def generate_jwt(self):
        now = int(time.time())
        payload = {"iss": "cdp", "nbf": now, "exp": now + 120, "sub": API_KEY}
        headers = {"kid": API_KEY, "nonce": uuid.uuid4().hex}
        try:
            return jwt.encode(payload, API_SECRET, algorithm="ES256", headers=headers)
        except Exception as e:
            print(f"JWT generation failed: {e}")
            return None

    def on_open(self, ws):
        token = self.generate_jwt()
        if not token:
            print("Failed to generate JWT, check API credentials.")
            return
        ws.send(json.dumps({
            "type": "subscribe",
            "product_ids": [self.PRODUCT_ID],
            "channel": "candles",
            "granularity": self.GRANULARITY,
            "jwt": token
        }))
        print(f"SUBSCRIBE SENT for {self.PRODUCT_ID} candles")
        ws.send(json.dumps({"type": "subscribe", "channel": "heartbeat", "jwt": token}))
        print("SUBSCRIBE SENT for heartbeat")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception as e:
            print("Invalid JSON:", e)
            return

        if data.get("type") == "error":
            print("WS ERROR:", data.get("message"))
            return
        if data.get("channel") == "subscriptions":
            return
        if data.get("channel") != "candles":
            return

        for ev in data.get("events", []):
            if ev.get("type") not in ("snapshot", "update"):
                continue
            for c in ev.get("candles", []):
                try:
                    t = pd.to_datetime(int(c["start"]), unit="s")
                except:
                    t = pd.to_datetime(float(c["start"]), unit="s")
                row = {"time": t,
                       "open": float(c.get("open", 0)),
                       "high": float(c.get("high", 0)),
                       "low": float(c.get("low", 0)),
                       "close": float(c.get("close", 0)),
                       "volume": float(c.get("volume", 0))}
                self.h.loc[len(self.h)] = row
                self.h = self.h.iloc[-self.HISTORY_LEN:].reset_index(drop=True)
                self.evaluate()

    def on_error(self, ws, error):
        print("WebSocket error:", error)

    def on_close(self, ws, code, msg):
        print(f"WebSocket closed {code}: {msg}")
        if self.should_reconnect:
            print("Reconnecting WebSocket...")
            time.sleep(5)
            self.start_ws()

    def evaluate(self):
        if len(self.h) < self.BB_PERIOD + 2:
            return
        df = self.h.copy()
        df["wma"] = ta.wma(df["close"], length=self.WMA_PERIOD)
        bb = ta.bbands(df["close"], length=self.BB_PERIOD, std=self.BB_STD)
        cols = [c for c in bb.columns if c.startswith(("BBL", "BBM", "BBU"))]
        if len(cols) < 3:
            return
        df[["bb_low", "bb_mid", "bb_up"]] = bb[cols]

        last = df.iloc[-1]
        self.current_wma = Decimal(str(last.wma))
        price = Decimal(str(last.close))
        win = f"{self.GRANULARITY // 60}min"
        fl = str(last.close)
        sl = str(last.wma)
        cl = str(last.bb_mid)
        strat = "BBands"
        tf = win
        es = ""
        exit_sig = ""
        deviation = abs(price - self.current_wma) / self.current_wma if self.current_wma != Decimal('0') else Decimal('0')
        dyn = str(deviation)

        print(f"[{last.time}] Close={price:.5f} | BB_mid={last.bb_mid:.5f} | WMA={last.wma:.5f} | Deviation={deviation:.4f}")

        buy_cond = (not self.in_position and price > Decimal(str(last.bb_mid)) and price > self.current_wma and deviation > Decimal('0.0001'))
        sell_cond = (self.in_position and price < self.current_wma and deviation > Decimal('0.0001'))

        if buy_cond:
            es = "uptrend_swap"
            self.do_buy(price, win, fl, sl, cl, strat, es, exit_sig, tf, dyn)
        elif sell_cond:
            exit_sig = "downtrend_swap"
            self.do_sell(price, win, fl, sl, cl, strat, es, exit_sig, tf, dyn)
        else:
            print(f"[{last.time}] Hold. Last close: {price:.5f}")

    def do_buy(self, price, win, fl, sl, cl, strat, es, exit_sig, tf, dyn):
        metric_diff = abs(price - self.current_wma) if self.current_wma is not None else Decimal('0')
        print(f"[{datetime.now(timezone.utc)}] ▶ BUY signal at {price:.5f} (USD size: 1), metric_diff: {metric_diff:.6f}")
        cid = str(uuid.uuid4())
        try:
            resp = self.rest.market_order_buy(
                client_order_id=cid,
                product_id=self.PRODUCT_ID,
                quote_size="1"
            )
            info = resp.to_dict()
            print("BUY response:", info)
            time.sleep(2)
            accounts = self.rest.get_accounts().accounts
            post_bal = Decimal(next(a.available_balance['value'] for a in accounts if a.currency == 'DOGE'))
            prev_bal = post_bal - Decimal(info['success_response'].get('order_configuration', {}).get('market_market_ioc', {}).get('quote_size', 1)) / price
            bought = post_bal - prev_bal
            bought = Decimal(format(float(bought), ".4f"))
            if bought > 0:
                self.position_amount = bought
                self.last_buy_price = price
                self.in_position = True
                self.trades.append({
                    'side': 'BUY',
                    'time': datetime.now(timezone.utc),
                    'price': price,
                    'size': bought,
                    'signal_triggered': es,
                    'metric_diff': metric_diff
                })
                print(f"  ➔ Recorded BUY of {bought} DOGE @ {price}")
                self.log_trade(
                    win=win, fl=fl, sl=sl, cl=cl, strat=strat,
                    es=es, exit_sig="", tf=tf,
                    entry=f"{bought}@{price}",
                    fee=str(float(price) * float(bought) * float(self.FEE_RATE)),
                    sold="", pnl="", dyn=dyn
                )

                # Update oversight stats & query LLM advice every 5 trades
                pnl, win_rate, trades_count = get_current_stats(self.trades)
                self.oversight.update_stats(pnl, win_rate, trades_count)
                if trades_count > 0 and trades_count % 5 == 0:
                    advice = self.oversight.query_llm_for_advice("How can I improve the bot's performance?")
                    print("LLM Advice:\n", advice)
                    self.log_llm_advice(advice)

            else:
                print("  ➔ No fill detected, will retry on next signal.")
        except Exception as e:
            print("Buy failed:", e)

    def do_sell(self, price, win, fl, sl, cl, strat, es, exit_sig, tf, dyn):
        metric_diff = abs(price - self.current_wma) if self.current_wma is not None else Decimal('0')
        print(f"[{datetime.now(timezone.utc)}] ▶ SELL signal at {price:.5f} (DOGE amount: {self.position_amount}), metric_diff: {metric_diff:.6f}")
        try:
            prod = self.rest.get_product(self.PRODUCT_ID)
            step = Decimal(prod['base_increment'])
            amt = self.position_amount.quantize(step, rounding=ROUND_DOWN)
            amt_str = format_doge_amt(amt)
            cid = str(uuid.uuid4())
            resp = self.rest.market_order_sell(
                client_order_id=cid,
                product_id=self.PRODUCT_ID,
                base_size=amt_str
            )
            info = resp.to_dict()
            print("SELL response:", info)
            self.trades.append({
                'side': 'SELL',
                'time': datetime.now(timezone.utc),
                'price': price,
                'size': amt,
                'signal_triggered': exit_sig,
                'metric_diff': metric_diff
            })
            print(f"  ➔ Recorded SELL of {amt_str} DOGE @ {price}")
            self.in_position = False
            self.position_amount = Decimal('0')
            last_buy = self.trades[-2] if len(self.trades) >= 2 and self.trades[-2]['side'] == 'BUY' else None
            entry_price = last_buy['price'] if last_buy else ""
            entry_amt = last_buy['size'] if last_buy else ""
            gross = float(price) * float(amt)
            buy_gross = float(entry_price) * float(entry_amt) if last_buy else 0
            fee = gross * float(self.FEE_RATE)
            buy_fee = buy_gross * float(self.FEE_RATE)
            pnl = gross - fee - (buy_gross + buy_fee) if last_buy else ""
            self.log_trade(
                win=win, fl=fl, sl=sl, cl=cl, strat=strat,
                es="", exit_sig=exit_sig, tf=tf,
                entry=f"{entry_amt}@{entry_price}",
                fee=f"{buy_fee}+{fee}",
                sold=f"{amt}@{price}",
                pnl=pnl, dyn=dyn
            )

            # Update oversight stats & query LLM advice every 5 trades
            pnl, win_rate, trades_count = get_current_stats(self.trades)
            self.oversight.update_stats(pnl, win_rate, trades_count)
            if trades_count > 0 and trades_count % 5 == 0:
                advice = self.oversight.query_llm_for_advice("How can I improve the bot's performance?")
                print("LLM Advice:\n", advice)
                self.log_llm_advice(advice)

        except Exception as e:
            print("Sell failed:", e)

    def print_summary(self):
        if not self.trades:
            print("No trades this session.")
            return
        print("\nSession Trade Summary:")
        total_buy = sum(t['size'] * t['price'] for t in self.trades if t['side'] == 'BUY')
        total_sell = sum(t['size'] * t['price'] for t in self.trades if t['side'] == 'SELL')
        pnl = total_sell - total_buy
        for t in self.trades:
            print(f"{t['time']} - {t['side']} {t['size']} @ {t['price']} | Signal: {t.get('signal_triggered', '')} | Metric Diff: {t.get('metric_diff', '')}")
        print(f"Total Bought: {total_buy}, Total Sold: {total_sell}, P&L: {pnl}")

    def start_ws(self):
        ws_app = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        print("Starting WebSocket loop with keep-alive pings...")
        ws_app.run_forever(ping_interval=30, ping_timeout=10)

    def run(self):
        self.should_reconnect = True
        self.start_ws()

if __name__ == '__main__':
    print("=== LIVE DOGE WMA/BBAND TRADE ORCHESTRATOR ===")
    DogeTrader().run()
