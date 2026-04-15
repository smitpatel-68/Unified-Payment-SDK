# 💳 Unified Payment SDK — Fiat + Stablecoin Checkout Infrastructure

> A product case study on building merchant-facing payment infrastructure that seamlessly integrates traditional banking rails (cards, UPI, SEPA) with stablecoin rails (USDC, USDT) — providing a single API and checkout experience across all payment types.

---

## The Problem

Merchants operating cross-border face a fragmented payment landscape:

- **Fiat rails** (cards, bank transfers, local payment methods) are slow, expensive for cross-border, and require separate integrations per region
- **Stablecoin rails** (USDC, USDT on Polygon, Solana, Base) are fast and cheap, but require crypto-specific infrastructure that most merchants don't have
- **No unified product exists** that lets a merchant accept both fiat and crypto through a single integration, with one reconciliation format and one webhook contract

This project designs that unified product — from API spec to settlement mechanics to compliance handling.

---

## Key Product Decisions

### Decision 1: Single API Contract for Both Rails
One `POST /v1/payments` endpoint accepts both fiat and crypto. The `payment_method` field determines which engine processes it. The response format is identical regardless of rail — same webhook, same receipt, same reconciliation. Merchant engineering teams shouldn't care about rail internals.

### Decision 2: Merchant-Controlled vs Auto Rail Selection
**Decision: Hybrid.** Merchant configures which payment methods are available per region (e.g., enable UPI for India, USDC for global, cards everywhere). Within those options, the customer chooses. The platform recommends the optimal option via a `recommended: true` flag.

### Decision 3: Crypto Settlement Model
**Decision: Merchant chooses.** Crypto-native merchants want stablecoins directly. Traditional merchants want fiat. The `settlement_preference` config supports `"crypto"`, `"fiat"`, or `"auto"`.

### Decision 4: Gas Fee Handling
Gas is included in the quoted price to the customer, absorbed by the platform, and charged to the merchant as part of processing fee. The customer never sees gas. This mirrors card processing fees — invisible to the buyer.

### Decision 5: Multi-Chain Wallet Connection
Accept payment on whatever chain the customer's wallet holds funds. Use Circle CCTP to bridge to the merchant's preferred chain if needed. The customer never bridges manually.

---

## Blockchain Settlement Mechanics

### How a Stablecoin Payment Settles

```
Customer clicks "Pay with USDC"
    │
    ▼
1. Wallet Connection
   SDK detects: chain, token balance, wallet address
    │
    ▼
2. Payment Intent Created
   merchant_address, amount (6 decimals), chain, expiry (5 min rate lock)
    │
    ▼
3. Transaction Signing
   Customer signs ERC-20 transfer (or SPL on Solana)
   TX submitted to mempool
    │
    ▼
4. Confirmation Monitoring
   Polygon: 128 blocks (~4 min) | Solana: 1 slot (~400ms)
   Ethereum: 12 blocks (~2.5 min) | Base: 1 block (~2 sec)
    │
    ▼
5. Settlement
   Crypto: USDC stays in merchant wallet
   Fiat: Off-ramp via Circle Mint → bank deposit (same-day / T+1)
    │
    ▼
6. Reconciliation
   Webhook: payment.completed (tx_hash, block, confirmations, net_amount)
```

### Gas Optimization Strategy

| Payment Amount | Recommended Chain | Gas Cost | Gas % | Rationale |
|---|---|---|---|---|
| < $10 | Base | ~$0.0005 | 0.005% | Lowest absolute cost |
| $10 - $500 | Polygon | ~$0.001 | <0.01% | Best cost/liquidity balance |
| $500 - $10K | Polygon or Solana | ~$0.001 | <0.001% | High liquidity, fast finality |
| $10K - $100K | Polygon | ~$0.001 | <0.00001% | Institutional-grade, low fees |
| > $100K | Ethereum | ~$4.50 | <0.005% | Highest security guarantees |

### Digital Wallet Integration Matrix

| Wallet | Chains | Connection | Notes |
|---|---|---|---|
| MetaMask | All EVM | WalletConnect v2 / injected | Most popular. Chain switching. |
| Phantom | Solana, EVM | Phantom SDK | Native Solana. Added EVM 2024. |
| Coinbase Wallet | All EVM, Solana | Coinbase SDK | Deep Base integration. |
| Trust Wallet | All EVM, Solana, Tron | WalletConnect v2 | Widest chain support. Popular in SEA. |

---

## Compliance Layer

### Dual-Rail Compliance Requirements

| Requirement | Fiat Rail | Crypto Rail |
|---|---|---|
| KYC/KYB | Standard merchant onboarding | Same + wallet verification |
| Transaction monitoring | Fraud scoring (Stripe Radar) | KYT via Chainalysis |
| Sanctions screening | OFAC/EU/UN lists | Wallet address screening + KYT |
| Travel Rule | N/A for card payments | Required for >$3,000 (FATF) |
| Data protection | PCI DSS for card data | No card data; wallet addresses are public |
| Dispute resolution | Chargeback process | No chargebacks (irreversible). Escrow optional. |

### Security Architecture

- **Wallet connection:** Non-custodial. Platform never holds customer private keys.
- **Transaction signing:** Customer signs in their own wallet. Platform submits unsigned tx, wallet signs.
- **Merchant custody:** Merchant's receiving wallet is platform-managed (MPC) or self-hosted.
- **Smart contract risk:** No custom smart contracts. Uses standard ERC-20/SPL `transfer()` only.
- **Rate locking:** FX rate locked for 5 minutes. If tx confirms after expiry, payment is refunded.
- **Replay protection:** Nonce management per chain. Idempotency key on API requests.
- **Double-spend prevention:** Wait for required confirmations before marking payment as completed.

---

## Simulator

### Payment Flow Simulator
8 scenarios covering card, UPI, SEPA, USDC (Polygon/Solana/Base/Ethereum), and USDT (Tron).

```bash
python simulator/payment_flow.py --demo
```

### Gas Optimization Engine
Analyzes gas costs across 6 chains with cost ratings and time-of-day optimization.

```bash
python simulator/gas_optimizer.py --demo
python simulator/gas_optimizer.py --amount 500 --token USDC
```

---

## Repo Structure

```
unified-payment-sdk/
├── README.md
├── docs/
│   ├── prd.md                        ← Product Requirements Document
│   ├── settlement-mechanics.md       ← Fiat and crypto settlement flows
│   └── wallet-integration.md         ← Digital wallet connection specs
├── diagrams/
│   └── flows.md                      ← Mermaid sequence diagrams
├── api-spec/
│   └── openapi.yaml                  ← Unified Payment API contract
├── simulator/
│   ├── payment_flow.py               ← End-to-end payment simulator (8 scenarios)
│   └── gas_optimizer.py              ← Gas cost analysis across 6 chains
└── sdk/
    └── checkout.jsx                  ← React checkout widget (interactive demo)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Wallet Connection | WalletConnect v2, Phantom SDK, Coinbase SDK |
| EVM Transactions | ethers.js / viem — ERC-20 approve + transfer |
| Solana Transactions | @solana/web3.js — SPL token transfer |
| Gas Estimation | Alchemy Gas Manager, Solana Priority Fees API |
| Cross-Chain Bridge | Circle CCTP |
| Fiat Processing | Stripe (cards), local rail integrations (UPI/PIX/SEPA) |
| Compliance | Chainalysis KYT (crypto), PCI DSS (cards), OFAC screening |
| FX Rates | CoinGecko (crypto), Open Exchange Rates (fiat) |
| Monitoring | Alchemy Notify (EVM), Helius (Solana) |

---

*Product case study demonstrating crypto payment infrastructure design — stablecoin/fiat integration, digital wallet flows, blockchain settlement mechanics, gas optimization, and unified merchant experience.*
