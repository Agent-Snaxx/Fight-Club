# MIT License
# ORCA Oversight Regulator Comptroller Authority
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
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # Load .env file for OPENAI_API_KEY

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment. Please set it in your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

# --------- LLM fallback logic ----------
def safe_llm_call(prompt, models=None, max_tokens=250, temperature=0.7):
    if models is None:
        models = [
            "gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"
        ]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            answer = response.choices[0].message.content
            return answer, model
        except Exception as e:
            print(f"LLM {model} failed: {e}")
            continue
    return "No LLM model available. All attempts failed.", None

def format_params_for_human_readable(params: dict) -> str:
    descriptions = {
        "BB_period": "Bollinger Bands period (window size for volatility calculation).",
        "BB_STD": "Bollinger Bands standard deviation multiplier (band width).",
        "EMA_span": "EMA span (speed of trend detection).",
        "WMA_PERIOD": "Weighted Moving Average period (trend smoothing).",
        "GRANULARITY": "Candle timeframe in seconds (e.g., 300 = 5 minutes).",
        "HISTORY_LEN": "Number of candles stored for analysis.",
        "FEE_RATE": "Exchange trading fee rate (decimal).",
        "order_size": "Size of each order placed (in USD or base asset).",
        "max_buys": "Maximum number of buys allowed in a scaling strategy.",
        "max_trade_size_usd": "Maximum trade size allowed per trade in USD.",
        "deviation_threshold": "Minimum deviation threshold for trade triggers.",
        "velocity_window": "Window size to calculate velocity/momentum.",
        "stop_loss_pct": "Stop loss percentage for risk management.",
        "take_profit_pct": "Take profit percentage to secure gains.",
    }
    lines = []
    for k, v in params.items():
        desc = descriptions.get(k, "No description available.")
        lines.append(f"- {k}: {v} — {desc}")
    return "\n".join(lines)

class BotOversight:
    def __init__(self, initial_params=None):
        self.params = initial_params or {}
        self.trade_stats = {
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "trades_count": 0,
        }
        self.history = []
        self.llm_log = []

    def update_params(self, new_params: dict):
        self.params.update(new_params)

    def get_params_summary(self) -> str:
        return format_params_for_human_readable(self.params)

    def update_stats(self, pnl, win_rate, trades_count):
        self.trade_stats.update({
            "total_pnl": pnl,
            "win_rate": win_rate,
            "trades_count": trades_count,
        })
        self.history.append(self.trade_stats.copy())

    def query_llm_for_advice(self, question: str) -> str:
        prompt = (
            f"Bot parameters:\n{self.get_params_summary()}\n\n"
            f"Trade stats: Total PnL={self.trade_stats['total_pnl']:.4f}, "
            f"Win Rate={self.trade_stats['win_rate']:.2%}, "
            f"Trades Count={self.trade_stats['trades_count']}\n\n"
            f"Question: {question}\n\n"
            "Please provide detailed advice or parameter adjustment suggestions."
        )

        answer, model_used = safe_llm_call(prompt)
        # --- LOG the full prompt, answer, model, stats, params, timestamp ---
        self.llm_log.append({
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "question": question,
            "prompt": prompt,
            "answer": answer,
            "model": model_used,
            "params": dict(self.params),
            "trade_stats": dict(self.trade_stats),
        })
        return f"(LLM: {model_used}) {answer}"

    def save_history(self, path="oversight_history.json"):
        with open(path, "w") as f:
            json.dump(self.history, f, indent=2)

    def save_llm_log(self, path="oversight_llm_log.json"):
        with open(path, "w") as f:
            json.dump(self.llm_log, f, indent=2)

# === Test run example ===
if __name__ == "__main__":
    bot_oversight = BotOversight(initial_params={
        "BB_period": 20,
        "EMA_span": 14,
        "order_size": 1,
    })

    print("Parameter Summary:")
    print(bot_oversight.get_params_summary())

    bot_oversight.update_stats(pnl=10.5, win_rate=0.6, trades_count=10)
    advice = bot_oversight.query_llm_for_advice("How can I improve the bot's win rate?")
    print("\nLLM Advice:\n", advice)

    bot_oversight.save_history()
    bot_oversight.save_llm_log()
