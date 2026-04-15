# Settlement Mechanics — Fiat and Crypto Rails

## Fiat Settlement

### Card Payments (Visa/Mastercard via Stripe/Adyen)
- **Flow:** Customer → Card network → Acquirer → Platform → Merchant bank
- **Settlement:** T+1 (next business day). Funds available in merchant's Stripe/Adyen balance, then swept to bank.
- **Chargebacks:** 120-day dispute window. Platform handles on behalf of merchant.
- **Currency:** Settled in merchant's configured currency. FX handled by processor.

### UPI (India)
- **Flow:** Customer → UPI app (GPay/PhonePe) → NPCI → Platform's VPA → Merchant bank
- **Settlement:** Instant (real-time credit to platform's bank account). Merchant payout within minutes.
- **Chargebacks:** No chargeback mechanism. Refunds must be initiated by merchant.
- **Limits:** ₹1,00,000 per transaction (business VPA).

### PIX (Brazil)
- **Flow:** Customer → PIX key → BCB instant payment system → Platform → Merchant
- **Settlement:** Instant. 24/7/365 including holidays.
- **Chargebacks:** No native chargeback. Fraud disputes handled via judicial process.
- **FX:** BRL only. Cross-border PIX not yet available (expected 2026-2027).

### SEPA Credit Transfer (EU)
- **Flow:** Customer → IBAN transfer → EBA Clearing → Platform's EU bank → Merchant
- **Settlement:** 1 business day (SEPA Instant: 10 seconds, but not all banks support it).
- **Chargebacks:** No chargeback for credit transfers. Only for SEPA Direct Debit.

---

## Crypto Settlement

### Standard Flow (Merchant Receives Stablecoins)

```
Customer wallet ──[ERC-20 transfer]──► Platform monitoring address
                                            │
                                            ▼
                                    Confirmation wait
                                    (chain-specific)
                                            │
                                            ▼
                              Platform custody wallet receives USDC/USDT
                                            │
                                            ▼
                              Transfer to merchant's wallet address
                                            │
                                            ▼
                              Webhook: payment.completed
```

**Confirmation requirements (balancing speed vs security):**

| Chain | Confirmations | Time | Rationale |
|---|---|---|---|
| Polygon | 128 blocks | ~4 min | Reorg risk on PoS chains requires deeper confirmation |
| Ethereum | 12 blocks | ~2.5 min | Post-merge finality. 12 blocks = strong economic finality |
| Solana | 1 slot | ~400ms | Solana's Tower BFT provides fast deterministic finality |
| Base | 1 block | ~2 sec | L2 inherits Ethereum's security via fraud proofs |
| Tron | 19 blocks | ~1 min | Tron's DPoS requires 19 blocks for irreversibility |

### Hybrid Flow (Auto-Convert to Fiat)

```
Customer wallet ──[USDC transfer]──► Platform custody wallet
                                            │
                                            ▼
                                    On-chain confirmation
                                            │
                                            ▼
                              Off-ramp triggered automatically:
                              • Circle Mint API (USDC → USD, 1:1)
                              • Local off-ramp partner (for non-USD)
                                            │
                                            ▼
                              Fiat deposited to merchant bank
                              • Same-day if before cut-off (2pm ET for Circle)
                              • T+1 otherwise
                                            │
                                            ▼
                              Webhook: payment.completed
                              (includes both tx_hash AND bank_reference)
```

### Cross-Chain Settlement (CCTP)

When customer pays on Chain A but merchant wants funds on Chain B:

```
Customer ──[USDC on Solana]──► Platform custody (Solana)
                                        │
                                        ▼
                              Circle CCTP burn on Solana
                                        │
                                        ▼
                              Circle attestation service
                              (proves burn happened)
                                        │
                                        ▼
                              CCTP mint on Polygon
                              (fresh USDC minted)
                                        │
                                        ▼
                              Transfer to merchant wallet (Polygon)
```

**CCTP advantages over third-party bridges:**
- No liquidity pool risk (mint/burn model, not lock/unlock)
- No smart contract bridge risk (Circle is the sole trusted party)
- 1:1 conversion (no slippage)
- ~15-20 minutes total cross-chain time

---

## Reconciliation

### Unified Transaction Object

Both fiat and crypto payments produce the same reconciliation format:

```json
{
  "payment_id": "pay_a1b2c3d4e5f6",
  "status": "completed",
  "amount": { "value": 500.00, "currency": "USD" },
  "fee": { "value": 2.50, "currency": "USD" },
  "net_amount": { "value": 497.50, "currency": "USD" },
  "rail": "BLOCKCHAIN",
  "method": "USDC",
  "settlement": {
    "type": "crypto",
    "destination": "0xMerchantWallet...",
    "settled_at": "2026-03-15T14:22:33Z"
  },
  "blockchain": {
    "chain": "polygon",
    "tx_hash": "0xabc123...",
    "block_number": 54321000,
    "confirmations": 128
  },
  "created_at": "2026-03-15T14:18:00Z"
}
```

The `blockchain` field is `null` for fiat payments. Everything else is identical. This means the merchant's accounting system processes both rail types the same way.
