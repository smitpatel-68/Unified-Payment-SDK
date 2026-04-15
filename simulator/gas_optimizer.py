"""
Gas Optimization Engine

Analyzes gas costs across chains and recommends the optimal network
for a given payment amount and token.

Usage:
    python gas_optimizer.py --demo
    python gas_optimizer.py --amount 500 --token USDC
"""

import argparse
import random
from datetime import datetime, timezone

CHAINS = {
    "base": {
        "name": "Base", "tokens": ["USDC"],
        "base_gas_usd": 0.0005, "finality_sec": 2, "confirmations": 1,
        "liquidity": "HIGH", "notes": "Coinbase L2. Lowest gas for small payments.",
    },
    "solana": {
        "name": "Solana", "tokens": ["USDC"],
        "base_gas_usd": 0.00025, "finality_sec": 0.4, "confirmations": 1,
        "liquidity": "HIGH", "notes": "Fastest finality. Priority fees may apply during congestion.",
    },
    "polygon": {
        "name": "Polygon PoS", "tokens": ["USDC", "USDT"],
        "base_gas_usd": 0.001, "finality_sec": 240, "confirmations": 128,
        "liquidity": "HIGH", "notes": "Workhorse L2. Best cost/liquidity balance.",
    },
    "tron": {
        "name": "Tron", "tokens": ["USDT"],
        "base_gas_usd": 0.10, "finality_sec": 3, "confirmations": 19,
        "liquidity": "VERY HIGH", "notes": "Dominant USDT chain. Energy/bandwidth model.",
    },
    "arbitrum": {
        "name": "Arbitrum One", "tokens": ["USDC", "USDT"],
        "base_gas_usd": 0.002, "finality_sec": 5, "confirmations": 1,
        "liquidity": "HIGH", "notes": "Major L2. Strong DeFi liquidity.",
    },
    "ethereum": {
        "name": "Ethereum", "tokens": ["USDC", "USDT"],
        "base_gas_usd": 4.50, "finality_sec": 150, "confirmations": 12,
        "liquidity": "VERY HIGH", "notes": "Highest security. Only for >$10K payments.",
    },
}


def analyze_gas(amount, token="USDC"):
    print(f"\n{'=' * 70}")
    print(f"  ⛽ GAS OPTIMIZATION ENGINE")
    print(f"  Payment: ${amount:,.2f} in {token}")
    print(f"  Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 70}")

    results = []
    for key, chain in CHAINS.items():
        if token not in chain["tokens"]:
            continue
        gas = chain["base_gas_usd"] * (0.7 + random.random() * 0.6)
        gas_pct = (gas / amount) * 100 if amount > 0 else 0
        if gas_pct < 0.001: rating = "EXCELLENT"
        elif gas_pct < 0.01: rating = "GOOD"
        elif gas_pct < 0.1: rating = "ACCEPTABLE"
        elif gas_pct < 1: rating = "EXPENSIVE"
        else: rating = "PROHIBITIVE"

        results.append({
            "chain": key, "name": chain["name"], "gas_usd": gas,
            "gas_pct": gas_pct, "finality": chain["finality_sec"],
            "confirmations": chain["confirmations"], "liquidity": chain["liquidity"],
            "rating": rating, "notes": chain["notes"],
        })
    results.sort(key=lambda x: x["gas_usd"])

    if amount < 10: rec = "base" if token == "USDC" else "tron"; reason = "Lowest absolute gas for micro-payments"
    elif amount < 500: rec = "polygon"; reason = "Best cost/speed/liquidity balance"
    elif amount < 10000: rec = "polygon"; reason = "High liquidity with minimal gas"
    elif amount < 100000: rec = "polygon"; reason = "Institutional-grade with low fees"
    else: rec = "ethereum"; reason = "Highest security for large settlements"

    print(f"\n  {'Chain':<16} {'Gas Cost':<14} {'% of Amt':<12} {'Finality':<12} {'Liquidity':<12} Rating")
    print(f"  {'─'*16} {'─'*14} {'─'*12} {'─'*12} {'─'*12} {'─'*12}")
    for r in results:
        marker = "★" if r["chain"] == rec else " "
        fin = f"{r['finality']}s" if r["finality"] < 60 else f"{r['finality']/60:.1f}m"
        print(f"  {marker} {r['name']:<14} ${r['gas_usd']:<13.6f} {r['gas_pct']:<11.6f}% {fin:<11} {r['liquidity']:<11} {r['rating']}")

    print(f"\n  ✅ RECOMMENDATION: {CHAINS[rec]['name']}")
    print(f"     {reason}")

    eth = next((r for r in results if r["chain"] == "ethereum"), None)
    best = next((r for r in results if r["chain"] == rec), None)
    if eth and best and rec != "ethereum":
        savings = eth["gas_usd"] - best["gas_usd"]
        print(f"\n  💰 Savings vs Ethereum: ${savings:.4f}/tx ({savings/eth['gas_usd']*100:.1f}% reduction)")

    hour = datetime.now(timezone.utc).hour
    if 2 <= hour <= 8: print(f"\n  🕐 Low-activity window. Gas ~20-30% below daily average.")
    elif 14 <= hour <= 20: print(f"\n  🕐 Peak US hours. Gas may be elevated.")
    else: print(f"\n  🕐 Average gas conditions.")
    print(f"{'=' * 70}\n")


def run_demo():
    print("\n" + "=" * 70)
    print("  ⛽ GAS OPTIMIZATION ENGINE — DEMO")
    print("=" * 70)
    for amt, tok, label in [
        (5, "USDC", "Micro-payment ($5)"),
        (150, "USDC", "Standard ($150)"),
        (500, "USDT", "Medium USDT ($500)"),
        (5000, "USDC", "Large B2B ($5K)"),
        (75000, "USDC", "Enterprise ($75K)"),
        (250000, "USDC", "Treasury ($250K)"),
    ]:
        print(f"\n{'━' * 70}")
        print(f"  📋 {label}")
        analyze_gas(amt, tok)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gas Optimization Engine")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--amount", type=float, default=500)
    parser.add_argument("--token", type=str, default="USDC", choices=["USDC", "USDT"])
    args = parser.parse_args()
    if args.demo: run_demo()
    else: analyze_gas(args.amount, args.token)
