# Payment Flow Diagrams

## 1. Unified Checkout Flow (Customer Perspective)

```mermaid
sequenceDiagram
    participant C as Customer
    participant SDK as Checkout SDK
    participant API as Payment API
    participant FE as Fiat Engine
    participant CE as Crypto Engine
    participant M as Merchant

    C->>SDK: Opens checkout
    SDK->>API: GET /v1/methods (merchant config)
    API-->>SDK: Available methods (card, UPI, USDC, USDT)
    SDK-->>C: Display payment options

    alt Customer selects Card
        C->>SDK: Enters card details
        SDK->>API: POST /v1/payments (method: card)
        API->>FE: Process card payment
        FE-->>API: Payment confirmed (T+1 settlement)
        API-->>SDK: payment.completed
        SDK-->>C: Receipt shown
        API->>M: Webhook: payment.completed
    else Customer selects USDC
        C->>SDK: Connects wallet (MetaMask)
        SDK->>API: POST /v1/payments (method: usdc, chain: polygon)
        API->>CE: Create payment intent
        CE-->>API: Payment intent + gas estimate
        API-->>SDK: Sign request
        SDK->>C: "Sign transaction in wallet"
        C->>SDK: Signs in MetaMask
        SDK->>API: POST /v1/payments/{id}/confirm (tx_hash)
        API->>CE: Monitor on-chain
        CE-->>API: Confirmed (128 blocks)
        API-->>SDK: payment.completed
        SDK-->>C: Receipt shown
        API->>M: Webhook: payment.completed
    end
```

## 2. Crypto Settlement Flow

```mermaid
flowchart TD
    A[Customer signs tx in wallet] --> B[Tx broadcast to mempool]
    B --> C{Chain?}
    C -->|Polygon| D[Wait 128 blocks ~4min]
    C -->|Solana| E[Wait 1 slot ~400ms]
    C -->|Base| F[Wait 1 block ~2sec]
    C -->|Ethereum| G[Wait 12 blocks ~2.5min]
    C -->|Tron| H[Wait 19 blocks ~1min]
    
    D --> I[Payment confirmed]
    E --> I
    F --> I
    G --> I
    H --> I
    
    I --> J{Merchant settlement preference?}
    J -->|crypto| K[Transfer to merchant wallet]
    J -->|fiat| L[Trigger off-ramp]
    J -->|auto| M{Merchant has wallet?}
    M -->|yes| K
    M -->|no| L
    
    L --> N[Circle Mint / local off-ramp]
    N --> O[Fiat to merchant bank]
    
    K --> P[Webhook: payment.completed]
    O --> P
```

## 3. Gas Optimization Decision Tree

```mermaid
flowchart TD
    A[Payment amount] --> B{Amount < $10?}
    B -->|Yes| C[Base — $0.0005 gas]
    B -->|No| D{Amount < $500?}
    D -->|Yes| E[Polygon — $0.001 gas]
    D -->|No| F{Amount < $10K?}
    F -->|Yes| G[Polygon or Solana]
    F -->|No| H{Amount < $100K?}
    H -->|Yes| I[Polygon — institutional grade]
    H -->|No| J[Ethereum — max security]
    
    G --> K{Priority = speed?}
    K -->|Yes| L[Solana — 400ms]
    K -->|No| E
    
    C --> M[Check gas spike]
    E --> M
    L --> M
    I --> M
    J --> M
    
    M --> N{Current gas > 2x average?}
    N -->|Yes| O[Delay 30 min or switch chain]
    N -->|No| P[Proceed with payment]
```

## 4. Compliance Flow (Dual-Rail)

```mermaid
flowchart TD
    A[Payment initiated] --> B{Rail type?}
    
    B -->|Fiat| C[Standard KYC check]
    C --> D[Fraud scoring — Stripe Radar / Adyen Risk]
    D --> E{Score > threshold?}
    E -->|Pass| F[Process fiat payment]
    E -->|Fail| G[Block + manual review]
    
    B -->|Crypto| H[Wallet address screening]
    H --> I[KYT — Chainalysis risk score]
    I --> J{Risk score?}
    J -->|0-39 Low| K[Auto-approve]
    J -->|40-74 Medium| L[Flag for review]
    J -->|75-100 High| M[Block payment]
    
    K --> N{Amount > $3,000?}
    N -->|Yes| O[Collect Travel Rule data]
    N -->|No| P[Process crypto payment]
    O --> P
    
    L --> Q[Compliance team review — 4hr SLA]
    Q -->|Approved| P
    Q -->|Rejected| M
```

## 5. Cross-Chain Bridge Flow (CCTP)

```mermaid
sequenceDiagram
    participant CW as Customer Wallet (Solana)
    participant Platform as Platform
    participant CCTP as Circle CCTP
    participant MW as Merchant Wallet (Polygon)

    CW->>Platform: USDC transfer on Solana
    Platform->>Platform: Confirm on Solana (1 slot)
    Platform->>CCTP: Burn USDC on Solana
    CCTP->>CCTP: Generate attestation
    CCTP->>Platform: Attestation received
    Platform->>CCTP: Mint USDC on Polygon
    CCTP->>MW: Fresh USDC on Polygon
    Platform->>Platform: Webhook: payment.completed
```
