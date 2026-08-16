#!/usr/bin/env python3
"""
Daily Crypto Context Briefing
==============================
Answers one question: "Should I be more or less selective with Metasignals alerts today?"

Run: python briefing.py
"""

import os
import json
import datetime
from pathlib import Path

import requests
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")

CLAUDE_MODEL = os.getenv("BRIEFING_MODEL", "claude-sonnet-4-20250514")

REQUEST_TIMEOUT = 15  # seconds per API call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url: str, headers: dict | None = None, params: dict | None = None) -> dict | list | None:
    """GET with timeout and basic error handling. Returns None on failure."""
    try:
        r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [warn] API call failed: {url[:80]}… — {e}")
        return None


def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def _usd(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


# ---------------------------------------------------------------------------
# Section 1: Regime Signal
# ---------------------------------------------------------------------------

def fetch_regime_signal() -> dict:
    """BTC price/changes, dominance, total mcap change, Fear & Greed."""
    data = {}

    # --- CoinGecko: BTC price & market data ---
    cg = _get(
        "https://api.coingecko.com/api/v3/coins/bitcoin",
        params={
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        },
    )
    if cg and "market_data" in cg:
        md = cg["market_data"]
        data["btc_price"] = md.get("current_price", {}).get("usd")
        data["btc_24h_change_pct"] = md.get("price_change_percentage_24h")
        data["btc_7d_change_pct"] = md.get("price_change_percentage_7d")
    else:
        data["btc_price"] = None
        data["btc_24h_change_pct"] = None
        data["btc_7d_change_pct"] = None

    # --- CoinGecko: Global market data (dominance + total mcap) ---
    gd = _get("https://api.coingecko.com/api/v3/global")
    if gd and "data" in gd:
        g = gd["data"]
        data["btc_dominance"] = g.get("market_cap_percentage", {}).get("btc")
        data["total_mcap_change_24h_pct"] = g.get("market_cap_change_percentage_24h_usd")
    else:
        data["btc_dominance"] = None
        data["total_mcap_change_24h_pct"] = None

    # --- Alternative.me: Fear & Greed Index ---
    fg = _get("https://api.alternative.me/fng/?limit=2")
    if fg and "data" in fg and len(fg["data"]) >= 2:
        data["fear_greed_value"] = int(fg["data"][0]["value"])
        data["fear_greed_label"] = fg["data"][0]["value_classification"]
        data["fear_greed_prev"] = int(fg["data"][1]["value"])
    else:
        data["fear_greed_value"] = None
        data["fear_greed_label"] = None
        data["fear_greed_prev"] = None

    return data


def format_regime_signal(data: dict) -> str:
    lines = [
        "## Section 1: Regime Signal",
        "",
        f"BTC Price:          {_usd(data.get('btc_price'))}",
        f"BTC 24h Change:     {_pct(data.get('btc_24h_change_pct'))}",
        f"BTC 7d Change:      {_pct(data.get('btc_7d_change_pct'))}",
        "BTC Dominance:      {}".format(f"{data['btc_dominance']:.1f}%" if data.get('btc_dominance') else "N/A"),
        f"Total Mcap 24h:     {_pct(data.get('total_mcap_change_24h_pct'))}",
        "Fear & Greed:       {} ({}){}".format(
            data.get('fear_greed_value') or 'N/A',
            data.get('fear_greed_label') or 'N/A',
            f"  prev: {data['fear_greed_prev']}" if data.get("fear_greed_prev") else "",
        ),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 2: Participation & Flow
# ---------------------------------------------------------------------------

def fetch_participation_flow() -> dict:
    """Funding rates (Bybit), OI & ETF flows (CoinGlass)."""
    data = {}

    # --- Bybit public API: funding rates ---
    for symbol, key in [("BTCUSDT", "btc_funding"), ("ETHUSDT", "eth_funding")]:
        resp = _get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
        )
        if resp and resp.get("result") and resp["result"].get("list"):
            ticker = resp["result"]["list"][0]
            data[key] = float(ticker.get("fundingRate", 0))
        else:
            data[key] = None

    # --- CoinGlass: OI change & ETF flows (requires API key) ---
    cg_headers = {}
    if COINGLASS_API_KEY:
        cg_headers["coinglassSecret"] = COINGLASS_API_KEY

    if COINGLASS_API_KEY:
        # Open interest
        oi_resp = _get(
            "https://open-api.coinglass.com/public/v2/open_interest",
            headers=cg_headers,
            params={"symbol": "BTC", "time_type": "h24"},
        )
        if oi_resp and oi_resp.get("data"):
            data["btc_oi_change_pct"] = oi_resp["data"].get("changePercent")
        else:
            data["btc_oi_change_pct"] = None

        # ETF flows
        etf_resp = _get(
            "https://open-api.coinglass.com/public/v2/etf/flows",
            headers=cg_headers,
        )
        if etf_resp and etf_resp.get("data"):
            # Most recent day's net flow
            flows = etf_resp["data"]
            if isinstance(flows, list) and len(flows) > 0:
                data["btc_etf_net_flow"] = flows[-1].get("netFlow")
            else:
                data["btc_etf_net_flow"] = None
        else:
            data["btc_etf_net_flow"] = None
    else:
        data["btc_oi_change_pct"] = None
        data["btc_etf_net_flow"] = None

    return data


def format_participation_flow(data: dict) -> str:
    btc_f = data.get("btc_funding")
    eth_f = data.get("eth_funding")

    def _funding_str(val):
        if val is None:
            return "N/A"
        pct = val * 100
        flag = ""
        if pct > 0.03:
            flag = " ⚠ CROWDED LONG"
        elif pct < -0.03:
            flag = " ⚠ CROWDED SHORT"
        return f"{pct:.4f}%{flag}"

    lines = [
        "## Section 2: Participation & Flow",
        "",
        f"BTC Funding (Bybit): {_funding_str(btc_f)}",
        f"ETH Funding (Bybit): {_funding_str(eth_f)}",
        f"BTC OI Change 24h:   {_pct(data.get('btc_oi_change_pct')) if data.get('btc_oi_change_pct') else 'N/A (need CoinGlass key)'}",
        f"BTC ETF Net Flow:    {_usd(data.get('btc_etf_net_flow')) if data.get('btc_etf_net_flow') is not None else 'N/A (need CoinGlass key)'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 3: Macro Backdrop
# ---------------------------------------------------------------------------

def _yahoo_quote(symbol: str) -> tuple[float | None, float | None]:
    """Fetch latest close & 1-day change % from Yahoo Finance chart API."""
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?range=5d&interval=1d"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        # Filter out None values
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            current = closes[-1]
            prev = closes[-2]
            change = ((current - prev) / prev) * 100
            return round(current, 2), round(change, 2)
    except Exception as e:
        print(f"  [warn] Yahoo {symbol}: {e}")
    return None, None


def fetch_macro_backdrop() -> dict:
    """VIX, DXY, US10Y via Yahoo Finance chart API."""
    data = {}

    tickers = {
        "^VIX": "vix",
        "DX-Y.NYB": "dxy",
        "^TNX": "us10y",
    }

    for symbol, key in tickers.items():
        level, change = _yahoo_quote(symbol)
        data[f"{key}_level"] = level
        data[f"{key}_change_pct"] = change

    # --- Economic calendar: ForexFactory-style high-impact events ---
    # Using TradingEconomics free calendar as a best-effort
    today = datetime.date.today().isoformat()
    cal = _get(
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    )
    data["macro_events_today"] = []
    if cal and isinstance(cal, list):
        for evt in cal:
            evt_date = evt.get("date", "")[:10]
            impact = evt.get("impact", "").lower()
            if evt_date == today and impact in ("high",):
                data["macro_events_today"].append({
                    "title": evt.get("title", "Unknown"),
                    "time": evt.get("date", "")[11:16],
                    "country": evt.get("country", ""),
                    "impact": evt.get("impact", ""),
                })

    return data


def format_macro_backdrop(data: dict) -> str:
    vix = data.get("vix_level")
    vix_chg = data.get("vix_change_pct")
    dxy = data.get("dxy_level")
    dxy_chg = data.get("dxy_change_pct")
    us10y = data.get("us10y_level")
    us10y_chg = data.get("us10y_change_pct")

    vix_flag = ""
    if vix and vix > 25:
        vix_flag = " ⚠ ELEVATED"
    if vix_chg and vix_chg > 10:
        vix_flag = " ⚠ SPIKING"

    dxy_flag = ""
    if dxy_chg and dxy_chg > 0.5:
        dxy_flag = " — headwind for crypto longs"

    events = data.get("macro_events_today", [])
    event_lines = []
    fomc_cpi_nfp = False
    for evt in events:
        title = evt["title"]
        if any(kw in title.upper() for kw in ["FOMC", "CPI", "NFP", "NON-FARM", "NONFARM", "FED INTEREST"]):
            fomc_cpi_nfp = True
            event_lines.append(f"  *** HARD SKIP WARNING: {title} at {evt['time']} UTC ***")
        else:
            event_lines.append(f"  - {title} at {evt['time']} UTC ({evt['country']})")

    lines = [
        "## Section 3: Macro Backdrop",
        "",
        f"VIX:   {vix if vix else 'N/A'} ({_pct(vix_chg)}){vix_flag}",
        f"DXY:   {dxy if dxy else 'N/A'} ({_pct(dxy_chg)}){dxy_flag}",
        f"US10Y: {f'{us10y:.2f}%' if us10y else 'N/A'} ({_pct(us10y_chg)})",
        "",
        f"High-Impact Events Today: {len(events)} found",
    ]
    if fomc_cpi_nfp:
        lines.append("  ⚠⚠⚠ FOMC/CPI/NFP DAY — DO NOT TRADE ±30 MIN OF RELEASE ⚠⚠⚠")
    if event_lines:
        lines.extend(event_lines)
    elif not events:
        lines.append("  None scheduled.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 4: On-Chain Quick Read
# ---------------------------------------------------------------------------

def fetch_onchain_quick_read() -> dict:
    """
    On-chain metrics from CoinGlass (if key available) or CoinGecko proxies.
    This section is a learning layer — approximations are fine.
    """
    data = {}

    # Stablecoin market cap from CoinGecko (USDT + USDC)
    for coin, key in [("tether", "usdt_mcap"), ("usd-coin", "usdc_mcap")]:
        resp = _get(
            f"https://api.coingecko.com/api/v3/coins/{coin}",
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
            },
        )
        if resp and "market_data" in resp:
            data[key] = resp["market_data"].get("market_cap", {}).get("usd")
            data[f"{key}_change_24h"] = resp["market_data"].get("market_cap_change_percentage_24h")
        else:
            data[key] = None
            data[f"{key}_change_24h"] = None

    # BTC exchange reserves & whale count — best-effort from CoinGlass
    if COINGLASS_API_KEY:
        headers = {"coinglassSecret": COINGLASS_API_KEY}
        er = _get(
            "https://open-api.coinglass.com/public/v2/exchange_reserve",
            headers=headers,
            params={"symbol": "BTC"},
        )
        if er and er.get("data"):
            data["btc_exchange_reserve"] = er["data"].get("totalReserve")
            data["btc_exchange_reserve_change"] = er["data"].get("changePercent")
        else:
            data["btc_exchange_reserve"] = None
            data["btc_exchange_reserve_change"] = None
    else:
        data["btc_exchange_reserve"] = None
        data["btc_exchange_reserve_change"] = None

    return data


def format_onchain_quick_read(data: dict) -> str:
    usdt_mcap = data.get("usdt_mcap")
    usdc_mcap = data.get("usdc_mcap")
    stable_total = None
    if usdt_mcap and usdc_mcap:
        stable_total = usdt_mcap + usdc_mcap

    usdt_chg = data.get("usdt_mcap_change_24h")
    usdc_chg = data.get("usdc_mcap_change_24h")

    reserve = data.get("btc_exchange_reserve")
    reserve_chg = data.get("btc_exchange_reserve_change")

    lines = [
        "## Section 4: On-Chain Quick Read",
        "",
        f"Stablecoin Mcap (USDT+USDC): {_usd(stable_total)}",
        f"  USDT 24h: {_pct(usdt_chg)}   USDC 24h: {_pct(usdc_chg)}",
        f"  (Growing = dry powder entering; shrinking = capital leaving)",
        "",
        f"BTC Exchange Reserve: {_usd(reserve) if reserve else 'N/A (need CoinGlass key)'}",
        f"  24h Change: {_pct(reserve_chg) if reserve_chg else 'N/A'}",
        f"  (Falling reserves = holders accumulating; rising = potential sell pressure)",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 5: Synthesis via Claude API
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are a crypto trading context analyst. You receive raw market data
organised into four sections: Regime Signal, Participation & Flow, Macro Backdrop, and On-Chain.

Your job is to synthesise this into a brief daily context briefing for a discretionary trader
who uses Metasignals alerts with a cohort-based sizing framework.

Your output MUST follow this exact structure:

1. **Regime Label**: Classify as exactly one of: Risk-On, Risk-Off, or Choppy/Unclear.
   - Risk-On: BTC up, dominance stable/falling, greed rising
   - Risk-Off: BTC down, dominance spiking, fear rising
   - Choppy/Unclear: mixed signals

2. **Key Flags**: 2-4 bullet points highlighting anything the trader must know RIGHT NOW.
   Focus on: extreme funding rates, macro event hard skips, elevated VIX, DXY headwinds,
   stablecoin flows. Skip anything that's neutral/normal.

3. **Today's Bias Statement**: Exactly 3 sentences. Example format:
   "Regime is [label]. [Most important flow/positioning observation].
   Bias: [normal/tight/very tight] selectivity, [any directional lean if signals support it]."

Rules:
- Be concise. The entire output should be readable in under 60 seconds.
- Never recommend specific trades or entries.
- If data is missing (N/A), acknowledge it and work with what's available.
- Tie everything back to whether the trader should be MORE or LESS selective today.
- Use plain language, not jargon-heavy analysis.
"""


def synthesise_briefing(section_texts: list[str], raw_data: dict) -> str:
    """Send structured data to Claude for synthesis."""
    if not ANTHROPIC_API_KEY:
        return (
            "## Section 5: Today's Bias Statement\n\n"
            "⚠ ANTHROPIC_API_KEY not set — skipping Claude synthesis.\n"
            "Set the key in your environment or .env file to enable this section.\n\n"
            "Raw data has been printed above for manual interpretation."
        )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    user_content = "Here is today's raw market data. Synthesise it into the briefing.\n\n"
    user_content += "\n\n---\n\n".join(section_texts)
    user_content += "\n\n---\n\nRaw data (JSON for precision):\n"
    user_content += json.dumps(raw_data, indent=2, default=str)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    synthesis = response.content[0].text
    return f"## Section 5: Today's Bias Statement\n\n{synthesis}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_dotenv_if_exists():
    """Minimal .env loader — no extra dependency needed."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
        # Re-read after loading
        global ANTHROPIC_API_KEY, COINGLASS_API_KEY
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")


def main():
    load_dotenv_if_exists()

    now = datetime.datetime.now(datetime.timezone.utc)
    header = (
        f"# Daily Crypto Context Briefing\n"
        f"Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"{'=' * 50}"
    )
    print(header)
    print()

    # Collect all raw data and formatted sections
    all_data = {}
    section_texts = []

    # Section 1
    print("Fetching regime signal…")
    regime = fetch_regime_signal()
    all_data["regime"] = regime
    s1 = format_regime_signal(regime)
    section_texts.append(s1)
    print(s1)
    print()

    # Section 2
    print("Fetching participation & flow…")
    flow = fetch_participation_flow()
    all_data["participation"] = flow
    s2 = format_participation_flow(flow)
    section_texts.append(s2)
    print(s2)
    print()

    # Section 3
    print("Fetching macro backdrop…")
    macro = fetch_macro_backdrop()
    all_data["macro"] = macro
    s3 = format_macro_backdrop(macro)
    section_texts.append(s3)
    print(s3)
    print()

    # Section 4
    print("Fetching on-chain data…")
    onchain = fetch_onchain_quick_read()
    all_data["onchain"] = onchain
    s4 = format_onchain_quick_read(onchain)
    section_texts.append(s4)
    print(s4)
    print()

    # Section 5: Claude synthesis
    print("Generating synthesis…")
    print()
    s5 = synthesise_briefing(section_texts, all_data)
    print(s5)
    print()
    print("=" * 50)
    print("End of briefing. Trade with discipline.")


if __name__ == "__main__":
    main()
