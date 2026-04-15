import { useState, useEffect, useCallback, useRef } from "react";

// ─── SIMULATED DATA ───
const FX_RATES = {
  USD_INR: 83.45, USD_PHP: 56.12, USD_EUR: 0.92, USD_GBP: 0.79,
  USDC_USD: 1.0001, USDT_USD: 0.9998,
};

const NETWORKS = {
  polygon: { name: "Polygon", icon: "⬡", fee: 0.001, time: "~2 min", color: "#8247E5" },
  solana: { name: "Solana", icon: "◎", fee: 0.00025, time: "~400ms", color: "#14F195" },
  ethereum: { name: "Ethereum", icon: "⟠", fee: 4.50, time: "~3 min", color: "#627EEA" },
  base: { name: "Base", icon: "🔵", fee: 0.0005, time: "~2 sec", color: "#0052FF" },
};

const PAYMENT_METHODS = {
  card: { id: "card", label: "Credit / Debit Card", icon: "💳", type: "fiat", fee: "2.9% + $0.30", time: "Instant" },
  upi: { id: "upi", label: "UPI", icon: "📱", type: "fiat", fee: "Free", time: "Instant", region: "India" },
  sepa: { id: "sepa", label: "SEPA Transfer", icon: "🏦", type: "fiat", fee: "€0.20", time: "1 business day", region: "EU" },
  usdc: { id: "usdc", label: "USDC", icon: "💲", type: "crypto", fee: "Network gas only", time: "Depends on chain" },
  usdt: { id: "usdt", label: "USDT", icon: "₮", type: "crypto", fee: "Network gas only", time: "Depends on chain" },
};

// ─── MOCK TRANSACTION ENGINE ───
function generateTxHash() {
  const chars = "0123456789abcdef";
  return "0x" + Array.from({ length: 64 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function simulatePayment(method, network, amount) {
  return new Promise((resolve) => {
    const delay = method.type === "crypto" ? 2500 : 1500;
    setTimeout(() => {
      const fee = method.type === "crypto"
        ? (network ? NETWORKS[network].fee : 0.001)
        : method.id === "card" ? amount * 0.029 + 0.30 : 0;
      resolve({
        tx_id: `pay_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
        tx_hash: method.type === "crypto" ? generateTxHash() : null,
        status: "COMPLETED",
        method: method.label,
        network: network ? NETWORKS[network].name : null,
        amount_usd: amount,
        fee_usd: Math.round(fee * 100) / 100,
        net_amount: Math.round((amount - fee) * 100) / 100,
        settlement_time: method.type === "crypto" && network ? NETWORKS[network].time : method.time,
        timestamp: new Date().toISOString(),
        rail: method.type === "fiat" ? "TRADITIONAL" : "BLOCKCHAIN",
      });
    }, delay);
  });
}

// ─── WEBHOOK PAYLOAD GENERATOR ───
function generateWebhook(receipt) {
  return {
    event: "payment.completed",
    api_version: "2026-03-01",
    created: Math.floor(Date.now() / 1000),
    data: {
      object: {
        id: receipt.tx_id,
        object: "payment",
        amount: receipt.amount_usd * 100,
        currency: "usd",
        status: "succeeded",
        payment_method: receipt.method.toLowerCase().replace(/\s+/g, "_"),
        rail: receipt.rail,
        blockchain: receipt.network ? {
          network: receipt.network.toLowerCase(),
          tx_hash: receipt.tx_hash,
          confirmations: receipt.network === "Solana" ? 1 : 12,
        } : null,
        fee: { amount: receipt.fee_usd * 100, currency: "usd" },
        metadata: {},
        created: Math.floor(Date.now() / 1000),
      },
    },
  };
}

// ─── COMPONENTS ───

function StepIndicator({ steps, current }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", gap: 4, marginBottom: 28 }}>
      {steps.map((_, i) => (
        <div key={i} style={{
          width: i === current ? 24 : 8, height: 8,
          borderRadius: 4,
          background: i === current ? "#00d4aa" : i < current ? "#00d4aa80" : "#1e293b",
          transition: "all 0.3s ease",
        }} />
      ))}
    </div>
  );
}

function MethodCard({ method, selected, onClick }) {
  const isSelected = selected === method.id;
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 14,
        padding: "14px 16px", borderRadius: 10,
        background: isSelected ? "#0f2a23" : "#0a0f18",
        border: `1.5px solid ${isSelected ? "#00d4aa" : "#1a2236"}`,
        cursor: "pointer", transition: "all 0.2s",
        transform: isSelected ? "scale(1.01)" : "scale(1)",
      }}
    >
      <span style={{ fontSize: 22 }}>{method.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#e8edf5", fontFamily: "'DM Sans', sans-serif" }}>{method.label}</div>
        <div style={{ fontSize: 11, color: "#5a6b82", marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>
          {method.fee} · {method.time}{method.region ? ` · ${method.region}` : ""}
        </div>
      </div>
      <div style={{
        width: 18, height: 18, borderRadius: "50%",
        border: `2px solid ${isSelected ? "#00d4aa" : "#2a3654"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        transition: "all 0.2s",
      }}>
        {isSelected && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#00d4aa" }} />}
      </div>
    </div>
  );
}

function NetworkSelector({ selected, onSelect }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, color: "#5a6b82", marginBottom: 10, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
        SELECT NETWORK
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {Object.entries(NETWORKS).map(([key, net]) => (
          <div
            key={key}
            onClick={() => onSelect(key)}
            style={{
              padding: "12px 14px", borderRadius: 8,
              background: selected === key ? "#0f2a23" : "#0a0f18",
              border: `1.5px solid ${selected === key ? net.color : "#1a2236"}`,
              cursor: "pointer", transition: "all 0.2s",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 14 }}>{net.icon}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#e8edf5" }}>{net.name}</span>
            </div>
            <div style={{ fontSize: 10, color: "#5a6b82", marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
              ${net.fee} · {net.time}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Receipt({ receipt, webhook }) {
  const [showWebhook, setShowWebhook] = useState(false);
  return (
    <div style={{ animation: "fadeUp 0.5s ease" }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div style={{
          width: 56, height: 56, borderRadius: "50%",
          background: "linear-gradient(135deg, #00d4aa, #00b894)",
          display: "flex", alignItems: "center", justifyContent: "center",
          margin: "0 auto 16px", fontSize: 28,
          animation: "pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)",
        }}>✓</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#e8edf5" }}>Payment Successful</div>
        <div style={{ fontSize: 13, color: "#5a6b82", marginTop: 4 }}>{receipt.method} via {receipt.rail} rail</div>
      </div>

      <div style={{
        background: "#0a0f18", borderRadius: 10, padding: 20,
        border: "1px solid #1a2236",
      }}>
        {[
          ["Transaction ID", receipt.tx_id],
          receipt.tx_hash ? ["Tx Hash", receipt.tx_hash.slice(0, 18) + "..." + receipt.tx_hash.slice(-6)] : null,
          receipt.network ? ["Network", receipt.network] : null,
          ["Amount", `$${receipt.amount_usd.toFixed(2)}`],
          ["Fee", `$${receipt.fee_usd.toFixed(2)}`],
          ["Net Amount", `$${receipt.net_amount.toFixed(2)}`],
          ["Settlement", receipt.settlement_time],
          ["Timestamp", new Date(receipt.timestamp).toLocaleString()],
        ].filter(Boolean).map(([label, value], i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "10px 0",
            borderBottom: i < 7 ? "1px solid #111827" : "none",
          }}>
            <span style={{ fontSize: 12, color: "#5a6b82" }}>{label}</span>
            <span style={{ fontSize: 12, color: "#e8edf5", fontFamily: "'JetBrains Mono', monospace", textAlign: "right", maxWidth: "60%", wordBreak: "break-all" }}>{value}</span>
          </div>
        ))}
      </div>

      <button
        onClick={() => setShowWebhook(!showWebhook)}
        style={{
          width: "100%", marginTop: 16, padding: "10px",
          background: "#0a0f18", border: "1px solid #1a2236",
          borderRadius: 8, color: "#00d4aa", fontSize: 12,
          fontFamily: "'JetBrains Mono', monospace",
          cursor: "pointer", transition: "all 0.2s",
        }}
      >
        {showWebhook ? "Hide" : "View"} Webhook Payload (payment.completed)
      </button>

      {showWebhook && (
        <pre style={{
          marginTop: 12, padding: 16, background: "#060a10",
          borderRadius: 8, border: "1px solid #1a2236",
          fontSize: 10, color: "#00d4aa", overflow: "auto",
          fontFamily: "'JetBrains Mono', monospace",
          lineHeight: 1.6, maxHeight: 260,
        }}>
          {JSON.stringify(webhook, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── MAIN CHECKOUT ───
export default function UnifiedCheckout() {
  const [step, setStep] = useState(0);
  const [amount, setAmount] = useState("150.00");
  const [currency, setCurrency] = useState("USD");
  const [selectedMethod, setSelectedMethod] = useState(null);
  const [selectedNetwork, setSelectedNetwork] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [webhook, setWebhook] = useState(null);
  const [fxRate, setFxRate] = useState(null);

  const method = selectedMethod ? PAYMENT_METHODS[selectedMethod] : null;
  const isCrypto = method?.type === "crypto";

  // Simulate live FX rate updates
  useEffect(() => {
    if (isCrypto && selectedNetwork) {
      const interval = setInterval(() => {
        const base = selectedMethod === "usdc" ? 1.0001 : 0.9998;
        const jitter = (Math.random() - 0.5) * 0.0004;
        setFxRate(Math.round((base + jitter) * 10000) / 10000);
      }, 3000);
      setFxRate(selectedMethod === "usdc" ? 1.0001 : 0.9998);
      return () => clearInterval(interval);
    }
  }, [isCrypto, selectedNetwork, selectedMethod]);

  const handlePay = useCallback(async () => {
    if (!method) return;
    setProcessing(true);
    const result = await simulatePayment(method, selectedNetwork, parseFloat(amount));
    const wh = generateWebhook(result);
    setReceipt(result);
    setWebhook(wh);
    setProcessing(false);
    setStep(3);
  }, [method, selectedNetwork, amount]);

  const reset = () => {
    setStep(0);
    setSelectedMethod(null);
    setSelectedNetwork(null);
    setReceipt(null);
    setWebhook(null);
    setProcessing(false);
  };

  const steps = ["Amount", "Method", "Confirm", "Receipt"];
  const canProceed = step === 0 ? parseFloat(amount) > 0
    : step === 1 ? selectedMethod && (!isCrypto || selectedNetwork)
    : step === 2;

  return (
    <div style={{
      minHeight: "100vh",
      background: "radial-gradient(ellipse at 30% 0%, #0a1628 0%, #060a10 50%, #030508 100%)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20, fontFamily: "'DM Sans', sans-serif",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
      <style>{`
        @keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pop { 0% { transform: scale(0); } 80% { transform: scale(1.1); } 100% { transform: scale(1); } }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>

      <div style={{
        width: "100%", maxWidth: 420,
        background: "#0c1220",
        borderRadius: 16,
        border: "1px solid #1a2236",
        boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,212,170,0.05)",
        overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "20px 24px 16px",
          borderBottom: "1px solid #111827",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div>
            <div style={{ fontSize: 11, color: "#5a6b82", fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1.5, marginBottom: 4 }}>UNIFIED CHECKOUT</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#e8edf5" }}>Pay with any rail</div>
          </div>
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            background: "#0a2e20", padding: "4px 10px", borderRadius: 20,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00d4aa", animation: "pulse 2s infinite" }} />
            <span style={{ fontSize: 10, color: "#00d4aa", fontFamily: "'JetBrains Mono', monospace" }}>LIVE</span>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: "24px" }}>
          <StepIndicator steps={steps} current={step} />

          {/* Step 0: Amount */}
          {step === 0 && (
            <div style={{ animation: "fadeUp 0.3s ease" }}>
              <div style={{ fontSize: 12, color: "#5a6b82", marginBottom: 8, fontFamily: "'JetBrains Mono', monospace" }}>PAYMENT AMOUNT</div>
              <div style={{
                display: "flex", alignItems: "center", gap: 10,
                background: "#0a0f18", borderRadius: 10,
                border: "1.5px solid #1a2236", padding: "12px 16px",
              }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: "#00d4aa" }}>$</span>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  style={{
                    flex: 1, background: "transparent", border: "none",
                    color: "#e8edf5", fontSize: 28, fontWeight: 700,
                    fontFamily: "'DM Sans', sans-serif", outline: "none",
                  }}
                />
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  style={{
                    background: "#111827", border: "1px solid #1a2236",
                    color: "#e8edf5", padding: "6px 10px", borderRadius: 6,
                    fontSize: 13, fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                  <option value="INR">INR</option>
                </select>
              </div>
              <div style={{ fontSize: 11, color: "#3a4a62", marginTop: 8, fontFamily: "'JetBrains Mono', monospace" }}>
                Merchant: acme-marketplace.com · Order #ORD-2026-4891
              </div>
            </div>
          )}

          {/* Step 1: Method Selection */}
          {step === 1 && (
            <div style={{ animation: "fadeUp 0.3s ease" }}>
              <div style={{ fontSize: 12, color: "#5a6b82", marginBottom: 12, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>FIAT RAILS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                {["card", "upi", "sepa"].map(id => (
                  <MethodCard key={id} method={PAYMENT_METHODS[id]} selected={selectedMethod} onClick={() => { setSelectedMethod(id); setSelectedNetwork(null); }} />
                ))}
              </div>

              <div style={{ fontSize: 12, color: "#5a6b82", marginBottom: 12, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>STABLECOIN RAILS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {["usdc", "usdt"].map(id => (
                  <MethodCard key={id} method={PAYMENT_METHODS[id]} selected={selectedMethod} onClick={() => { setSelectedMethod(id); setSelectedNetwork("polygon"); }} />
                ))}
              </div>

              {isCrypto && <NetworkSelector selected={selectedNetwork} onSelect={setSelectedNetwork} />}
            </div>
          )}

          {/* Step 2: Confirm */}
          {step === 2 && method && (
            <div style={{ animation: "fadeUp 0.3s ease" }}>
              <div style={{
                background: "#0a0f18", borderRadius: 12, padding: 20,
                border: "1px solid #1a2236", marginBottom: 16,
              }}>
                <div style={{ textAlign: "center", marginBottom: 20 }}>
                  <div style={{ fontSize: 36, fontWeight: 700, color: "#e8edf5" }}>${parseFloat(amount).toFixed(2)}</div>
                  <div style={{ fontSize: 12, color: "#5a6b82", marginTop: 4 }}>{currency}</div>
                </div>

                <div style={{ borderTop: "1px solid #111827", paddingTop: 16 }}>
                  {[
                    ["Payment Method", `${method.icon} ${method.label}`],
                    ["Rail", method.type === "fiat" ? "Traditional (Fiat)" : "Blockchain (Stablecoin)"],
                    isCrypto && selectedNetwork ? ["Network", `${NETWORKS[selectedNetwork].icon} ${NETWORKS[selectedNetwork].name}`] : null,
                    ["Fee", isCrypto && selectedNetwork ? `$${NETWORKS[selectedNetwork].fee}` : method.fee],
                    isCrypto && fxRate ? ["Exchange Rate", `1 ${selectedMethod.toUpperCase()} = $${fxRate}`] : null,
                    isCrypto && fxRate ? ["You Send", `${(parseFloat(amount) / fxRate).toFixed(4)} ${selectedMethod.toUpperCase()}`] : null,
                    ["Settlement", isCrypto && selectedNetwork ? NETWORKS[selectedNetwork].time : method.time],
                  ].filter(Boolean).map(([label, value], i) => (
                    <div key={i} style={{
                      display: "flex", justifyContent: "space-between",
                      padding: "8px 0", fontSize: 13,
                    }}>
                      <span style={{ color: "#5a6b82" }}>{label}</span>
                      <span style={{ color: "#e8edf5", fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {isCrypto && fxRate && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 8,
                  background: "#0a2e20", padding: "8px 12px", borderRadius: 8,
                  marginBottom: 16,
                }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00d4aa", animation: "pulse 2s infinite" }} />
                  <span style={{ fontSize: 11, color: "#00d4aa", fontFamily: "'JetBrains Mono', monospace" }}>
                    Rate refreshes every 3s · Locked on confirmation
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Receipt */}
          {step === 3 && receipt && <Receipt receipt={receipt} webhook={webhook} />}

          {/* Navigation */}
          {step < 3 && (
            <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
              {step > 0 && (
                <button
                  onClick={() => setStep(step - 1)}
                  style={{
                    flex: "0 0 auto", padding: "12px 20px",
                    background: "#0a0f18", border: "1px solid #1a2236",
                    borderRadius: 10, color: "#5a6b82", fontSize: 14,
                    fontWeight: 600, cursor: "pointer",
                  }}
                >←</button>
              )}
              <button
                onClick={() => step === 2 ? handlePay() : setStep(step + 1)}
                disabled={!canProceed || processing}
                style={{
                  flex: 1, padding: "14px 24px",
                  background: canProceed && !processing
                    ? "linear-gradient(135deg, #00d4aa, #00b894)"
                    : "#1a2236",
                  border: "none", borderRadius: 10,
                  color: canProceed ? "#030508" : "#3a4a62",
                  fontSize: 14, fontWeight: 700, cursor: canProceed ? "pointer" : "default",
                  transition: "all 0.2s",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                {processing ? (
                  <>
                    <div style={{ width: 16, height: 16, border: "2px solid #030508", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    {isCrypto ? "Broadcasting to " + NETWORKS[selectedNetwork]?.name + "..." : "Processing..."}
                  </>
                ) : step === 2 ? `Pay $${parseFloat(amount).toFixed(2)}` : "Continue"}
              </button>
            </div>
          )}

          {step === 3 && (
            <button
              onClick={reset}
              style={{
                width: "100%", marginTop: 16, padding: "12px",
                background: "transparent", border: "1px solid #1a2236",
                borderRadius: 10, color: "#5a6b82", fontSize: 13,
                fontWeight: 600, cursor: "pointer",
              }}
            >New Payment</button>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: "12px 24px",
          borderTop: "1px solid #111827",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: 10, color: "#2a3654", fontFamily: "'JetBrains Mono', monospace" }}>
            Powered by Unified Checkout SDK v1.0
          </span>
          <div style={{ display: "flex", gap: 12 }}>
            {["Fiat", "USDC", "USDT"].map(r => (
              <span key={r} style={{
                fontSize: 9, color: "#3a4a62",
                background: "#0a0f18", padding: "2px 6px",
                borderRadius: 4, fontFamily: "'JetBrains Mono', monospace",
              }}>{r}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
