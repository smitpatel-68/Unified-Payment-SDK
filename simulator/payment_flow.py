"""
Unified Payment Engine — Core Router

Single entry point for all payment types. Takes a payment intent and routes it
to the correct rail: Card, UPI, SEPA (fiat) or USDC/USDT on Polygon, Solana,
Ethereum, Base (crypto). Returns a unified PaymentResult regardless of rail.

This is the merchant-facing abstraction layer — merchants never think about
which rail to use. They submit a payment intent, and the engine handles routing,
fee calculation, compliance checks, and settlement tracking.

Usage:
    python payment_engine.py --demo     # Run all 8 demo scenarios
    python payment_engine.py            # Interactive mode
"""

import json
import random
import time
import argparse
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────
# Enums and Constants
# ─────────────────────────────────────────

class RailType(Enum):
    CARD = "card"
    UPI = "upi"
    SEPA = "sepa"
    SWIFT = "swift"
    USDC = "usdc"
    USDT = "usdt"

class NetworkType(Enum):
    POLYGON = "polygon"
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BASE = "base"
    TRON = "tron"

class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CONFIRMING = "confirming"           # On-chain: waiting for block confirmations
    SETTLED = "settled"
    FAILED = "failed"
    REQUIRES_ACTION = "requires_action"  # 3DS, wallet approval, etc.


# ─────────────────────────────────────────
# Network Configuration (Real-world data)
# ─────────────────────────────────────────

NETWORKS = {
    "polygon": {
        "name": "Polygon PoS",
        "chain_id": 137,
        "native_token": "MATIC",
        "avg_block_time_sec": 2.0,
        "confirmations_required": 12,
        "finality_type": "probabilistic",
        "avg_gas_gwei": 80,
        "gas_limit_erc20": 65000,
        "base_fee_usd": 0.001,
        "supported_stablecoins": ["USDC", "USDT"],
        "rpc_providers": ["Alchemy", "QuickNode", "Infura"],
        "usdc_contract": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "usdt_contract": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
    },
    "solana": {
        "name": "Solana",
        "chain_id": None,
        "native_token": "SOL",
        "avg_block_time_sec": 0.4,
        "confirmations_required": 1,
        "finality_type": "deterministic",
        "avg_compute_units": 200000,
        "base_fee_usd": 0.00025,
        "supported_stablecoins": ["USDC", "USDT"],
        "rpc_providers": ["Helius", "Triton", "QuickNode"],
        "usdc_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    },
    "ethereum": {
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "native_token": "ETH",
        "avg_block_time_sec": 12.0,
        "confirmations_required": 12,
        "finality_type": "probabilistic (PoS finality ~15min)",
        "avg_gas_gwei": 25,
        "gas_limit_erc20": 65000,
        "base_fee_usd": 4.50,
        "supported_stablecoins": ["USDC", "USDT", "DAI"],
        "rpc_providers": ["Alchemy", "Infura", "QuickNode"],
        "usdc_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "usdt_contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    },
    "base": {
        "name": "Base (Coinbase L2)",
        "chain_id": 8453,
        "native_token": "ETH",
        "avg_block_time_sec": 2.0,
        "confirmations_required": 12,
        "finality_type": "optimistic rollup (7-day challenge)",
        "avg_gas_gwei": 0.01,
        "gas_limit_erc20": 65000,
        "base_fee_usd": 0.0005,
        "supported_stablecoins": ["USDC", "USDT"],
        "rpc_providers": ["Alchemy", "QuickNode"],
        "usdc_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    },
    "tron": {
        "name": "Tron",
        "chain_id": None,
        "native_token": "TRX",
        "avg_block_time_sec": 3.0,
        "confirmations_required": 19,
        "finality_type": "DPoS (19 confirmations)",
        "base_fee_usd": 0.10,
        "supported_stablecoins": ["USDT"],
        "rpc_providers": ["TronGrid"],
        "usdt_contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "compliance_note": "Elevated AML risk. Enhanced KYT screening required.",
    },
}

FIAT_RAILS = {
    "card": {
        "name": "Credit / Debit Card",
        "fee_pct": 2.9,
        "fee_fixed_usd": 0.30,
        "settlement_time": "Instant authorization, T+2 settlement",
        "currencies": ["USD", "EUR", "GBP", "INR", "SGD", "AUD", "CAD"],
        "requires_3ds": True,
        "chargeback_risk": True,
    },
    "upi": {
        "name": "UPI (Unified Payments Interface)",
        "fee_pct": 0,
        "fee_fixed_usd": 0,
        "settlement_time": "Instant (< 30 seconds)",
        "currencies": ["INR"],
        "region": "India",
        "max_amount_inr": 100000,
        "requires_vpa": True,
    },
    "sepa": {
        "name": "SEPA Credit Transfer",
        "fee_pct": 0,
        "fee_fixed_usd": 0.20,
        "settlement_time": "1 business day (SEPA Instant: < 10 seconds)",
        "currencies": ["EUR"],
        "region": "EU/EEA",
        "iban_required": True,
    },
    "swift": {
        "name": "SWIFT MT103",
        "fee_pct": 0,
        "fee_fixed_usd": 35.00,
        "settlement_time": "2-5 business days",
        "currencies": ["USD", "EUR", "GBP", "SGD", "AUD", "CAD", "JPY"],
        "correspondent_banks": True,
        "nostro_prefunding": True,
    },
}


# ─────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────

@dataclass
class PaymentIntent:
    """What the merchant submits via API."""
    amount_usd: float
    currency: str = "USD"
    destination_country: str = "US"
    rail: str = "auto"              # "auto", "card", "upi", "sepa", "usdc", "usdt"
    network: str = "auto"           # "auto", "polygon", "solana", "ethereum", "base"
    priority: str = "balanced"      # "speed", "cost", "balanced"
    wallet_address: Optional[str] = None
    customer_email: Optional[str] = None
    metadata: dict = field(default_factory=dict)

@dataclass
class FeeBreakdown:
    rail_fee_usd: float
    network_fee_usd: float          # Gas fee (crypto only)
    fx_spread_usd: float
    total_fee_usd: float
    fee_pct_of_amount: float

@dataclass
class SettlementInfo:
    rail_type: str                  # "FIAT" or "BLOCKCHAIN"
    method: str                     # "card", "upi", "usdc", etc.
    network: Optional[str]          # "polygon", "solana" (crypto only)
    chain_id: Optional[int]
    tx_hash: Optional[str]
    block_number: Optional[int]
    confirmations: int
    confirmations_required: int
    finality_type: str
    estimated_settlement: str

@dataclass
class WalletInfo:
    """Digital wallet details for crypto payments."""
    wallet_type: str                # "metamask", "phantom", "walletconnect", "custodial"
    address: str
    chain: str
    connected_at: str
    balance_usd: Optional[float] = None

@dataclass
class PaymentResult:
    """Unified result object — same structure for fiat and crypto."""
    payment_id: str
    status: str
    amount_usd: float
    currency: str
    fees: FeeBreakdown
    settlement: SettlementInfo
    wallet: Optional[WalletInfo]
    receipt_url: str
    webhook_event: str
    created_at: str
    settled_at: Optional[str]
    decision_rationale: List[str]


# ─────────────────────────────────────────
# Gas Optimizer
# ─────────────────────────────────────────

class GasOptimizer:
    """Selects optimal chain based on amount, urgency, and current gas conditions."""

    @staticmethod
    def get_current_gas():
        """Simulate fetching live gas prices (in production: Alchemy/QuickNode APIs)."""
        return {
            "polygon": {"gas_gwei": random.randint(30, 200), "congestion": "low"},
            "solana": {"compute_units": 200000, "congestion": "low"},
            "ethereum": {"gas_gwei": random.randint(15, 80), "congestion": random.choice(["low", "medium", "high"])},
            "base": {"gas_gwei": round(random.uniform(0.005, 0.05), 3), "congestion": "low"},
            "tron": {"energy": 65000, "congestion": "low"},
        }

    @staticmethod
    def calculate_fee(network_key: str, gas_data: dict) -> float:
        """Calculate actual transaction fee in USD."""
        net = NETWORKS[network_key]
        base = net["base_fee_usd"]
        # Add congestion multiplier
        congestion = gas_data.get("congestion", "low")
        multiplier = {"low": 1.0, "medium": 1.5, "high": 3.0}[congestion]
        return round(base * multiplier, 6)

    @staticmethod
    def recommend(amount_usd: float, stablecoin: str, priority: str) -> tuple:
        """
        Returns (recommended_network, fee, rationale).
        
        Decision logic:
        - Amount > $100K → Ethereum (institutional trust, highest security)
        - Priority = speed → Solana (400ms finality)
        - Priority = cost → Base or Polygon (sub-cent fees)
        - USDT + cost priority → Tron (cheapest for USDT)
        - Default → Polygon (best balance of cost, speed, and ecosystem support)
        """
        gas = GasOptimizer.get_current_gas()
        rationale = []

        # Filter networks by stablecoin support
        candidates = {k: v for k, v in NETWORKS.items() if stablecoin in v["supported_stablecoins"]}

        if amount_usd > 100000:
            rationale.append(f"Amount ${amount_usd:,.0f} exceeds $100K → Ethereum for institutional settlement guarantees")
            return "ethereum", GasOptimizer.calculate_fee("ethereum", gas["ethereum"]), rationale

        if priority == "speed":
            if "solana" in candidates:
                rationale.append("Priority: speed → Solana (400ms deterministic finality)")
                return "solana", GasOptimizer.calculate_fee("solana", gas["solana"]), rationale
            rationale.append("Priority: speed → Base (2s block time, L2 speed)")
            return "base", GasOptimizer.calculate_fee("base", gas["base"]), rationale

        if priority == "cost":
            if stablecoin == "USDT" and "tron" in candidates:
                rationale.append("Priority: cost + USDT → Tron ($0.10, lowest for USDT)")
                rationale.append("⚠️ Tron: enhanced KYT screening applied (elevated AML risk profile)")
                return "tron", GasOptimizer.calculate_fee("tron", gas["tron"]), rationale
            # Compare Base vs Polygon
            base_fee = GasOptimizer.calculate_fee("base", gas["base"])
            polygon_fee = GasOptimizer.calculate_fee("polygon", gas["polygon"])
            if base_fee < polygon_fee:
                rationale.append(f"Priority: cost → Base (${base_fee:.4f} < Polygon ${polygon_fee:.4f})")
                return "base", base_fee, rationale
            rationale.append(f"Priority: cost → Polygon (${polygon_fee:.4f})")
            return "polygon", polygon_fee, rationale

        # Balanced: default to Polygon
        # Check if Polygon gas is spiked
        polygon_fee = GasOptimizer.calculate_fee("polygon", gas["polygon"])
        if gas["polygon"]["gas_gwei"] > 150:
            rationale.append(f"Polygon gas elevated ({gas['polygon']['gas_gwei']} gwei) → falling back to Base")
            base_fee = GasOptimizer.calculate_fee("base", gas["base"])
            return "base", base_fee, rationale

        rationale.append(f"Balanced priority → Polygon (${polygon_fee:.4f}, ~2min finality, broad ecosystem)")
        return "polygon", polygon_fee, rationale


# ─────────────────────────────────────────
# Rail Selection Engine
# ─────────────────────────────────────────

class RailSelector:
    """Determines optimal payment rail based on payment intent."""

    @staticmethod
    def select(intent: PaymentIntent) -> tuple:
        """
        Returns (rail_type, network_or_none, rationale).
        
        Auto-selection logic:
        1. If merchant specified a rail → use it
        2. If destination = India and amount < ₹1L → UPI
        3. If destination = EU → SEPA
        4. If amount < $10 → Card (crypto gas fees would be disproportionate)
        5. If amount > $50K and no wallet → SWIFT
        6. If wallet_address provided → Crypto (stablecoin)
        7. Default → Card
        """
        rationale = []

        if intent.rail != "auto":
            rationale.append(f"Merchant specified rail: {intent.rail}")
            if intent.rail in ("usdc", "usdt"):
                stablecoin = intent.rail.upper()
                network, gas_fee, gas_rationale = GasOptimizer.recommend(
                    intent.amount_usd, stablecoin, intent.priority
                )
                if intent.network != "auto":
                    network = intent.network
                    rationale.append(f"Merchant specified network: {network}")
                rationale.extend(gas_rationale)
                return intent.rail, network, rationale
            return intent.rail, None, rationale

        # Auto-selection
        if intent.destination_country == "IN" and intent.amount_usd * 83.5 < 100000:
            rationale.append(f"Destination: India, amount ₹{intent.amount_usd * 83.5:,.0f} < ₹1,00,000 → UPI")
            return "upi", None, rationale

        if intent.destination_country in ("DE", "FR", "NL", "ES", "IT", "BE", "AT", "IE", "PT", "FI"):
            rationale.append(f"Destination: EU ({intent.destination_country}) → SEPA")
            return "sepa", None, rationale

        if intent.amount_usd < 10:
            rationale.append(f"Amount ${intent.amount_usd} < $10 → Card (crypto gas disproportionate)")
            return "card", None, rationale

        if intent.wallet_address:
            rationale.append("Wallet address provided → routing to stablecoin rail")
            stablecoin = "usdc"  # Default to USDC
            network, gas_fee, gas_rationale = GasOptimizer.recommend(
                intent.amount_usd, stablecoin.upper(), intent.priority
            )
            rationale.extend(gas_rationale)
            return stablecoin, network, rationale

        if intent.amount_usd > 50000:
            rationale.append(f"Amount ${intent.amount_usd:,.0f} > $50K, no wallet → SWIFT (settlement certainty)")
            return "swift", None, rationale

        rationale.append("Default routing → Card")
        return "card", None, rationale


# ─────────────────────────────────────────
# Payment Processor
# ─────────────────────────────────────────

class PaymentProcessor:
    """Processes payments and returns unified results."""

    @staticmethod
    def _gen_id():
        return f"pay_{int(time.time())}_{random.randint(1000, 9999)}"

    @staticmethod
    def _gen_tx_hash():
        chars = "0123456789abcdef"
        return "0x" + "".join(random.choices(chars, k=64))

    @staticmethod
    def calculate_fees(rail: str, network: Optional[str], amount: float) -> FeeBreakdown:
        """Calculate fee breakdown for any rail."""
        if rail in FIAT_RAILS:
            config = FIAT_RAILS[rail]
            rail_fee = amount * (config["fee_pct"] / 100) + config["fee_fixed_usd"]
            return FeeBreakdown(
                rail_fee_usd=round(rail_fee, 2),
                network_fee_usd=0,
                fx_spread_usd=0,
                total_fee_usd=round(rail_fee, 2),
                fee_pct_of_amount=round(rail_fee / amount * 100, 3) if amount > 0 else 0,
            )
        else:
            # Crypto rail
            gas_data = GasOptimizer.get_current_gas()
            network_fee = GasOptimizer.calculate_fee(network, gas_data.get(network, {})) if network else 0.001
            return FeeBreakdown(
                rail_fee_usd=0,
                network_fee_usd=round(network_fee, 6),
                fx_spread_usd=0,
                total_fee_usd=round(network_fee, 6),
                fee_pct_of_amount=round(network_fee / amount * 100, 6) if amount > 0 else 0,
            )

    @staticmethod
    def build_settlement(rail: str, network: Optional[str]) -> SettlementInfo:
        """Build settlement info for any rail."""
        if rail in FIAT_RAILS:
            config = FIAT_RAILS[rail]
            return SettlementInfo(
                rail_type="FIAT",
                method=config["name"],
                network=None,
                chain_id=None,
                tx_hash=None,
                block_number=None,
                confirmations=0,
                confirmations_required=0,
                finality_type="banking_settlement",
                estimated_settlement=config["settlement_time"],
            )
        else:
            net = NETWORKS.get(network, {})
            block = random.randint(50000000, 60000000)
            confirmations = net.get("confirmations_required", 12)
            return SettlementInfo(
                rail_type="BLOCKCHAIN",
                method=rail.upper(),
                network=net.get("name", network),
                chain_id=net.get("chain_id"),
                tx_hash=PaymentProcessor._gen_tx_hash(),
                block_number=block,
                confirmations=confirmations,
                confirmations_required=confirmations,
                finality_type=net.get("finality_type", "unknown"),
                estimated_settlement=f"{net.get('avg_block_time_sec', 2) * confirmations:.0f}s ({confirmations} confirmations)",
            )

    @staticmethod
    def build_wallet(rail: str, network: Optional[str], intent: PaymentIntent) -> Optional[WalletInfo]:
        """Build wallet info for crypto payments."""
        if rail not in ("usdc", "usdt"):
            return None

        wallet_addr = intent.wallet_address or f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
        wallet_type = "metamask" if network in ("polygon", "ethereum", "base") else "phantom" if network == "solana" else "tronlink"

        return WalletInfo(
            wallet_type=wallet_type,
            address=wallet_addr,
            chain=network or "polygon",
            connected_at=datetime.now(timezone.utc).isoformat(),
            balance_usd=round(random.uniform(100, 50000), 2),
        )

    @staticmethod
    def process(intent: PaymentIntent) -> PaymentResult:
        """Main entry point — process a payment intent into a unified result."""
        # Step 1: Select rail
        rail, network, rationale = RailSelector.select(intent)

        # Step 2: Calculate fees
        fees = PaymentProcessor.calculate_fees(rail, network, intent.amount_usd)

        # Step 3: Build settlement info
        settlement = PaymentProcessor.build_settlement(rail, network)

        # Step 4: Build wallet info (crypto only)
        wallet = PaymentProcessor.build_wallet(rail, network, intent)

        # Step 5: Build result
        now = datetime.now(timezone.utc)
        return PaymentResult(
            payment_id=PaymentProcessor._gen_id(),
            status="SETTLED",
            amount_usd=intent.amount_usd,
            currency=intent.currency,
            fees=fees,
            settlement=settlement,
            wallet=wallet,
            receipt_url=f"https://checkout.example.com/receipt/{PaymentProcessor._gen_id()}",
            webhook_event="payment.completed",
            created_at=now.isoformat(),
            settled_at=(now + timedelta(seconds=random.randint(1, 10))).isoformat(),
            decision_rationale=rationale,
        )


# ─────────────────────────────────────────
# Webhook Generator
# ─────────────────────────────────────────

def generate_webhook(result: PaymentResult) -> dict:
    """Generate merchant webhook payload — unified format regardless of rail."""
    return {
        "event": result.webhook_event,
        "api_version": "2026-04-01",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": result.payment_id,
                "object": "payment",
                "amount": int(result.amount_usd * 100),
                "currency": result.currency.lower(),
                "status": result.status.lower(),
                "rail": result.settlement.rail_type,
                "payment_method": result.settlement.method,
                "blockchain": {
                    "network": result.settlement.network,
                    "chain_id": result.settlement.chain_id,
                    "tx_hash": result.settlement.tx_hash,
                    "block_number": result.settlement.block_number,
                    "confirmations": result.settlement.confirmations,
                    "finality": result.settlement.finality_type,
                } if result.settlement.rail_type == "BLOCKCHAIN" else None,
                "wallet": {
                    "type": result.wallet.wallet_type,
                    "address": result.wallet.address,
                    "chain": result.wallet.chain,
                } if result.wallet else None,
                "fees": {
                    "rail_fee": int(result.fees.rail_fee_usd * 100),
                    "network_fee": int(result.fees.network_fee_usd * 100),
                    "total_fee": int(result.fees.total_fee_usd * 100),
                    "currency": "usd",
                },
                "created": int(time.time()),
            },
        },
    }


# ─────────────────────────────────────────
# Pretty Printer
# ─────────────────────────────────────────

def print_result(intent: PaymentIntent, result: PaymentResult):
    """Print formatted payment result."""
    is_crypto = result.settlement.rail_type == "BLOCKCHAIN"

    print(f"\n  Payment: ${intent.amount_usd:,.2f} {intent.currency}")
    print(f"  Destination: {intent.destination_country}")
    if intent.rail != "auto":
        print(f"  Requested rail: {intent.rail}")
    if intent.wallet_address:
        print(f"  Wallet: {intent.wallet_address[:20]}...")

    print(f"\n  Decision Rationale:")
    for r in result.decision_rationale:
        print(f"    → {r}")

    print(f"\n  Settlement:")
    print(f"    Rail:        {result.settlement.rail_type}")
    print(f"    Method:      {result.settlement.method}")
    if is_crypto:
        print(f"    Network:     {result.settlement.network} (chain_id: {result.settlement.chain_id})")
        print(f"    Tx Hash:     {result.settlement.tx_hash[:30]}...")
        print(f"    Block:       #{result.settlement.block_number}")
        print(f"    Confirms:    {result.settlement.confirmations}/{result.settlement.confirmations_required}")
        print(f"    Finality:    {result.settlement.finality_type}")
    print(f"    Settlement:  {result.settlement.estimated_settlement}")

    if result.wallet:
        print(f"\n  Wallet:")
        print(f"    Type:        {result.wallet.wallet_type}")
        print(f"    Address:     {result.wallet.address[:20]}...{result.wallet.address[-6:]}")
        print(f"    Chain:       {result.wallet.chain}")
        print(f"    Balance:     ${result.wallet.balance_usd:,.2f}")

    print(f"\n  Fees:")
    print(f"    Rail fee:    ${result.fees.rail_fee_usd:.2f}")
    print(f"    Network fee: ${result.fees.network_fee_usd:.6f}")
    print(f"    Total:       ${result.fees.total_fee_usd:.4f} ({result.fees.fee_pct_of_amount:.4f}% of amount)")

    print(f"\n  Status:        ✅ {result.status}")
    print(f"  Payment ID:    {result.payment_id}")
    print("=" * 72)


# ─────────────────────────────────────────
# Demo Scenarios
# ─────────────────────────────────────────

DEMO_SCENARIOS = [
    {
        "name": "E-commerce card payment — US customer, $49.99",
        "intent": PaymentIntent(amount_usd=49.99, currency="USD", destination_country="US"),
    },
    {
        "name": "India payout via UPI — ₹5,000 (~$60)",
        "intent": PaymentIntent(amount_usd=60, currency="INR", destination_country="IN"),
    },
    {
        "name": "EU SEPA transfer — €500 to Germany",
        "intent": PaymentIntent(amount_usd=543, currency="EUR", destination_country="DE"),
    },
    {
        "name": "Crypto payment — USDC on Polygon, wallet provided",
        "intent": PaymentIntent(
            amount_usd=250, rail="usdc", network="auto",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        ),
    },
    {
        "name": "Speed-priority crypto — USDC, fastest settlement",
        "intent": PaymentIntent(
            amount_usd=1200, rail="usdc", priority="speed",
            wallet_address="SoLwALLeT1234567890abcdefghijklmnop",
        ),
    },
    {
        "name": "Cost-priority USDT — cheapest rail",
        "intent": PaymentIntent(
            amount_usd=800, rail="usdt", priority="cost",
            wallet_address="0xCostOptimized12345abcdef",
        ),
    },
    {
        "name": "Large enterprise wire — $250K, no wallet",
        "intent": PaymentIntent(amount_usd=250000, currency="USD", destination_country="SG"),
    },
    {
        "name": "Micro payment — $3 tip (card, crypto too expensive)",
        "intent": PaymentIntent(amount_usd=3.00, currency="USD", destination_country="US"),
    },
]


def run_demo():
    print("\n" + "=" * 72)
    print("  💳 UNIFIED PAYMENT SDK — Payment Engine Demo")
    print("  Fiat + Crypto rails in a single integration")
    print("=" * 72)
    print(f"  {len(DEMO_SCENARIOS)} scenarios | {len(FIAT_RAILS)} fiat rails | {len(NETWORKS)} blockchain networks")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")

    for scenario in DEMO_SCENARIOS:
        print(f"\n\n📋 Scenario: {scenario['name']}")
        result = PaymentProcessor.process(scenario["intent"])
        print_result(scenario["intent"], result)

    # Summary
    print("\n\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"\n  Rails demonstrated:")
    print(f"    Fiat:   Card, UPI, SEPA, SWIFT")
    print(f"    Crypto: USDC (Polygon, Solana, Base), USDT (Tron, Polygon)")
    print(f"\n  Key design decisions:")
    print(f"    • Unified PaymentResult regardless of rail")
    print(f"    • Auto rail selection based on amount, destination, wallet")
    print(f"    • Gas optimizer selects cheapest/fastest chain")
    print(f"    • Webhook format abstracts fiat vs blockchain")
    print(f"    • Merchant never needs to know which rail was used")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Payment Engine")
    parser.add_argument("--demo", action="store_true", help="Run demo scenarios")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        print("Use --demo to run scenarios. Interactive mode coming soon.")
