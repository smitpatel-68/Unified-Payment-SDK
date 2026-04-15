# Product Requirements Document — Unified Payment SDK
**Author:** Smit Patel
**Version:** 1.0
**Last Updated:** Q1 2026

---

## 1. Problem

Merchants selling cross-border face two separate payment worlds:

**Fiat world:** Cards (Visa/MC via Stripe/Adyen), local methods (UPI, PIX, SEPA, PromptPay), bank transfers. Mature but slow and expensive for cross-border. Each region requires a different integration.

**Crypto world:** Stablecoins (USDC, USDT) on multiple chains (Polygon, Solana, Base, Ethereum, Tron). Fast and cheap, but requires wallet infrastructure, gas management, chain selection, and compliance tooling that most merchants don't have.

No product today gives a merchant **one integration** that handles both worlds with a unified checkout, unified settlement, and unified reconciliation.

## 2. Target Users

- **Marketplaces** — Need to pay sellers in multiple countries. Want to accept both fiat and crypto from buyers.
- **B2B platforms** — Invoice-based payments where suppliers may prefer stablecoin settlement.
- **Web3 companies** — Already hold stablecoins. Need fiat acceptance for non-crypto customers.
- **Cross-border e-commerce** — Selling to SEA, LatAm, Africa where card penetration is low but mobile wallets and stablecoins are growing.

## 3. Solution

A single SDK and API that:

1. Presents the customer with all available payment methods (card, UPI, USDC, USDT, etc.) in one checkout
2. Routes the payment through the appropriate engine (fiat processor or blockchain)
3. Handles gas estimation, chain selection, and wallet connection for crypto payments
4. Settles to the merchant in their preferred format (fiat to bank, or stablecoins to wallet)
5. Produces a unified transaction record, webhook, and reconciliation format regardless of which rail was used

## 4. Functional Requirements

### Checkout Layer
- Embeddable JS widget, hosted checkout page, and mobile SDK
- Payment method selector showing fiat and crypto options
- Real-time FX rate display for stablecoin payments (refreshed every 3 seconds)
- Rate lock: 5-minute window after customer commits to pay
- Chain and wallet auto-detection when crypto is selected

### Fiat Engine
- Card processing via Stripe/Adyen (PCI DSS compliant, tokenized)
- Local payment methods: UPI (India), PIX (Brazil), SEPA (EU), PromptPay (Thailand)
- Standard settlement: T+1 for cards, instant for real-time methods

### Crypto Engine
- Wallet connection: WalletConnect v2, injected providers (MetaMask), Phantom SDK, Coinbase SDK
- Supported tokens: USDC (Polygon, Solana, Base, Ethereum), USDT (Polygon, Tron, Ethereum)
- Gas estimation: real-time across all supported chains
- Chain recommendation: based on amount, gas cost, and liquidity
- Transaction monitoring: webhook-based confirmation (Alchemy Notify for EVM, Helius for Solana)
- Confirmation thresholds: Polygon 128 blocks, Ethereum 12 blocks, Solana 1 slot, Base 1 block
- Cross-chain: Circle CCTP for bridging USDC between chains if needed

### Settlement Layer
- Fiat settlement: standard banking rails (T+1 card, instant UPI/PIX)
- Crypto settlement (merchant receives stablecoins): on-chain transfer to merchant wallet after confirmation
- Hybrid settlement (auto-convert): stablecoin received → off-ramp to fiat via Circle Mint or local partner → bank deposit
- Unified transaction object: same schema for fiat and crypto payments

### Compliance Layer
- KYC/KYB: merchant onboarding with identity verification
- KYT: Chainalysis integration for crypto transaction screening
- Sanctions: OFAC/EU/UN list screening on both wallet addresses and beneficiary names
- Travel Rule: originator/beneficiary data collection for crypto transfers >$3,000 (FATF threshold)
- PCI DSS: card data never touches merchant servers (tokenized via Stripe/Adyen)
- No smart contract risk: uses standard ERC-20 `transfer()` only. No custom contracts.

## 5. Non-Functional Requirements

- **Latency:** Checkout widget loads in <500ms. Gas estimate returned in <200ms.
- **Availability:** 99.95% uptime SLA for API. Blockchain monitoring has chain-specific failover RPCs.
- **Security:** Non-custodial wallet connection. MPC wallet option for merchant custody. Nonce management for replay protection. Idempotency keys on all API requests.
- **Scalability:** Horizontally scalable payment processing. Independent fiat and crypto engines.

## 6. Phased Delivery

### Phase 1: Fiat + USDC on Polygon (MVP)
- Card payments via Stripe
- USDC on Polygon with MetaMask wallet connection
- Fiat settlement only
- Basic compliance (KYC, sanctions screening)

### Phase 2: Multi-Chain + Multi-Wallet
- Add Solana (Phantom), Base (Coinbase Wallet), Ethereum
- Add USDT support (Polygon, Tron)
- Crypto settlement option for merchants
- KYT integration (Chainalysis)

### Phase 3: Full Coverage + Local Methods
- UPI, PIX, SEPA, PromptPay
- Cross-chain bridging via CCTP
- Travel Rule compliance
- Merchant dashboard with unified reconciliation

## 7. Success Metrics

| Metric | Target |
|---|---|
| Merchant integration time | <3 days (single SDK) |
| Checkout conversion rate | >65% (vs industry 45% average) |
| Crypto payment confirmation | <5 min (Polygon), <1 min (Solana/Base) |
| Settlement to merchant | Same-day for crypto, T+1 for card |
| Compliance screening | <500ms per transaction |
| Gas cost as % of payment | <0.01% for payments >$100 |
