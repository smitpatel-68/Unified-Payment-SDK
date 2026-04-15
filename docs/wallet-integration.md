# Digital Wallet Integration Specification

## Connection Flow

### Step 1: Wallet Detection
SDK scans for available wallet providers in the browser/mobile environment.

```
Check injected providers (window.ethereum, window.solana)
    │
    ├── MetaMask detected → offer MetaMask option
    ├── Phantom detected → offer Phantom option
    ├── Coinbase Wallet detected → offer Coinbase option
    └── None detected → offer WalletConnect QR code
```

### Step 2: Chain Detection
After wallet connects, SDK reads the active chain and token balances.

```
wallet.chainId → determine current chain
wallet.request({ method: 'eth_getBalance' }) → native token
ERC-20 balanceOf(wallet_address) → USDC/USDT balance
    │
    ├── Sufficient balance on current chain → proceed
    ├── Sufficient balance on different chain → prompt chain switch
    └── Insufficient balance → show "Insufficient funds" error
```

### Step 3: Chain Switching (if needed)
If customer's wallet is on Ethereum but Polygon is recommended (lower gas):

```
wallet.request({
  method: 'wallet_switchEthereumChain',
  params: [{ chainId: '0x89' }]  // Polygon
})
```

If chain not added to wallet:
```
wallet.request({
  method: 'wallet_addEthereumChain',
  params: [{ chainId, chainName, rpcUrls, ... }]
})
```

### Step 4: Transaction Signing
Platform constructs the unsigned transaction. Customer signs in their wallet.

**EVM (Polygon/Base/Ethereum):**
```
ERC-20 transfer(merchant_address, amount)
// amount in 6 decimals for USDC/USDT (e.g., 500 USDC = 500000000)
```

**Solana:**
```
SPL Token transfer instruction
// USDC mint: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
// amount in 6 decimals
```

**Tron:**
```
TRC-20 transfer(merchant_address, amount)
// USDT contract: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
// Uses energy/bandwidth instead of gas
```

## Security Considerations

### Non-Custodial Architecture
- Platform NEVER has access to customer's private keys
- Wallet connection is read-only until customer explicitly signs
- Platform constructs the transaction payload; wallet signs it
- If wallet connection drops, no funds are at risk

### Replay Protection
- Each transaction includes a nonce (EVM) or recent blockhash (Solana)
- Platform tracks nonces per wallet per chain to prevent double-submission
- Idempotency key on API side prevents duplicate payment creation

### Phishing Prevention
- SDK verifies the merchant's receiving address against platform registry
- Domain verification: SDK checks that the hosting domain matches the merchant's registered domain
- Transaction simulation: before signing, SDK shows the customer exactly what will happen (amount, destination, gas)

### Rate Lock Security
- FX rate locked for 5 minutes when customer reaches confirmation screen
- If blockchain confirmation takes longer than 5 minutes (e.g., Ethereum congestion), the platform absorbs the rate difference up to 0.5%
- Beyond 0.5% adverse movement: payment is automatically refunded to customer wallet

### Smart Contract Risk Mitigation
- NO custom smart contracts are used
- All payments use standard `transfer()` function on audited token contracts (Circle USDC, Tether USDT)
- No approve + transferFrom pattern (avoids infinite approval risk)
- No interaction with DEXs, bridges, or DeFi protocols during payment flow
