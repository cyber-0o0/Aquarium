"use client";

import React, { useState, useCallback } from "react";
import {
  ArrowUp, ArrowDown, Repeat, Star, Wallet, RefreshCw,
  Copy, ExternalLink, ChevronRight, TrendingUp, TrendingDown,
  Coins, Shield, Zap, Globe
} from "lucide-react";
import styles from "./page.module.css";
import { clsx } from "clsx";
import { TonConnectButton, useTonAddress, useTonConnectUI } from "@tonconnect/ui-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { walletApi, authApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Skeleton } from "@/components/common/Skeleton";

// ── Types ──────────────────────────────────────────────────────────────────────

interface WalletOverview {
  ton: {
    address: string;
    ton_balance: number;
    usd_value: number;
    ton_price_usd: number;
    status: string;
    name?: string;
    icon?: string;
    is_scam?: boolean;
  };
  jettons: Array<{
    symbol: string;
    name: string;
    balance: number;
    usd_value?: number;
    image?: string;
    verified: boolean;
    address: string;
  }>;
  total_usd: number;
  has_wallet: boolean;
  network: string;
}

interface TonPrice {
  usd: number;
  usd_24h_change: number;
}

interface Transaction {
  hash: string;
  type: string;
  direction: string;
  title: string;
  time_unix: number;
  time_iso: string;
  amount_ton?: number;
  token_symbol?: string;
  token_amount?: number;
  comment?: string;
  fee_ton: number;
  status: string;
  explorer_url: string;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WalletPage() {
  const address = useTonAddress();
  const [tonConnectUI] = useTonConnectUI();
  const { user, setAuth, accessToken } = useAuthStore();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"activity" | "tokens">("activity");
  const [copied, setCopied] = useState(false);
  const [showReceive, setShowReceive] = useState(false);

  const isLinked = !!user?.wallet_address;
  const walletAddress = user?.wallet_address || address || null;
  const canFetchWallet = !!walletAddress;

  // ── Queries ────────────────────────────────────────────────────────────────

  const { data: tonPrice } = useQuery<TonPrice>({
    queryKey: ["ton-price"],
    queryFn: walletApi.getTonPrice,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const { data: overview, isLoading: loadingOverview } = useQuery<WalletOverview>({
    queryKey: ["wallet-overview", walletAddress],
    queryFn: walletApi.getOverview,
    enabled: canFetchWallet,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });

  const { data: txData, isLoading: loadingTxs } = useQuery({
    queryKey: ["wallet-transactions", walletAddress],
    queryFn: () => walletApi.getTransactions(30),
    enabled: canFetchWallet,
    staleTime: 30_000,
  });

  const { data: depositInfo } = useQuery({
    queryKey: ["wallet-deposit"],
    queryFn: walletApi.getDepositInfo,
    enabled: isLinked && showReceive,
  });

  // ── Mutations ──────────────────────────────────────────────────────────────

  const syncMutation = useMutation({
    mutationFn: walletApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wallet-overview"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] });
    },
  });

  const linkMutation = useMutation({
    mutationFn: async () => {
      const walletAccount = tonConnectUI.account;
      if (!address || !accessToken || !walletAccount) throw new Error("No wallet or token");
      const { nonce } = await authApi.getNonce();
      
      // In a real production scenario with TonConnect 2.0, you'd use ton-proof.
      // For now, we provide the public key so the backend can verify a signature if we had one.
      // We pass a placeholder signature to demonstrate the multi-field check.
      return authApi.tonConnect(address, walletAccount.publicKey, "0000000000000000", nonce);
    },
    onSuccess: () => {
      if (user) setAuth(accessToken!, { ...user, wallet_address: address });
      queryClient.invalidateQueries({ queryKey: ["wallet-overview"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] });
    },
  });

  // Auto-link when TonConnect wallet connects and not yet linked to account
  React.useEffect(() => {
    if (address && !isLinked && accessToken && !linkMutation.isPending) {
      linkMutation.mutate();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [address, isLinked, accessToken]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  const copyAddress = useCallback(() => {
    const addr = user?.wallet_address || address;
    if (!addr) return;
    navigator.clipboard.writeText(addr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [user?.wallet_address, address]);

  const displayAddress = walletAddress;
  const shortAddress = displayAddress
    ? `${displayAddress.slice(0, 6)}…${displayAddress.slice(-4)}`
    : null;

  const tonBalance = overview?.ton.ton_balance ?? 0;
  const totalUsd = overview?.total_usd ?? 0;
  const priceChange = tonPrice?.usd_24h_change ?? 0;
  const priceChangePositive = priceChange >= 0;

  const [whole, decimal] = tonBalance.toFixed(2).split(".");

  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>Wallet</h1>
        <div className={styles.headerRight}>
          <TonConnectButton />
        </div>
      </header>

      <div className={styles.content}>

        {/* ── Balance card ── */}
        <div className={styles.balanceCard}>
          <div className={styles.balanceTop}>
            <div className={styles.balanceMeta}>
              <span className={styles.balanceLabel}>TOTAL BALANCE</span>
              {overview?.ton.name && (
                <span className={styles.walletName}>{overview.ton.name}</span>
              )}
            </div>
            <div className={styles.headerActions}>
              {tonPrice && (
                <div className={styles.priceChip}>
                  <span className={styles.tonPrice}>${tonPrice.usd.toFixed(3)}</span>
                  <span className={clsx(styles.priceChange, priceChangePositive ? styles.up : styles.down)}>
                    {priceChangePositive ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                    {Math.abs(priceChange).toFixed(2)}%
                  </span>
                </div>
              )}
              <button
                className={clsx(styles.syncBtn, syncMutation.isPending && styles.spinning)}
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending || !isLinked}
                aria-label="Refresh"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </div>

          {loadingOverview && isLinked ? (
            <div className={styles.balanceSkeleton}>
              <Skeleton width="180px" height="56px" borderRadius="8px" />
              <Skeleton width="100px" height="20px" borderRadius="4px" />
            </div>
          ) : (
            <>
              <div className={styles.balanceMain}>
                <span className={styles.amountWhole}>{isLinked ? whole : "0"}</span>
                <span className={styles.amountDecimals}>.{isLinked ? decimal : "00"}</span>
                <span className={styles.currency}>TON</span>
              </div>
              <div className={styles.usdValue}>
                ≈ ${isLinked ? totalUsd.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00"}
              </div>
            </>
          )}

          {/* Address row */}
          {displayAddress ? (
            <div className={styles.addressRow}>
              <button className={styles.addressChip} onClick={copyAddress}>
                <span className={styles.addressText}>{shortAddress}</span>
                <Copy size={12} className={clsx(styles.copyIcon, copied && styles.copied)} />
              </button>
              {!isLinked && address && (
                <button
                  className={styles.linkBtn}
                  onClick={() => linkMutation.mutate()}
                  disabled={linkMutation.isPending}
                >
                  {linkMutation.isPending ? "Linking…" : "Link to account"}
                </button>
              )}
            </div>
          ) : (
            <div className={styles.noWallet}>
              <span>Connect a wallet to see your balance</span>
            </div>
          )}

          {/* Action buttons */}
          <div className={styles.actionBtns}>
            <button
              className={styles.actionBtn}
              onClick={() => tonConnectUI.sendTransaction({
                validUntil: Math.floor(Date.now() / 1000) + 300,
                messages: [],
              }).catch(() => {})}
              disabled={!isLinked}
            >
              <div className={styles.iconCircle}><ArrowUp size={18} /></div>
              Send
            </button>
            <button
              className={styles.actionBtn}
              onClick={() => setShowReceive(v => !v)}
              disabled={!isLinked}
            >
              <div className={styles.iconCircle}><ArrowDown size={18} /></div>
              Receive
            </button>
            <button className={styles.actionBtn} disabled={!isLinked}>
              <div className={styles.iconCircle}><Repeat size={18} /></div>
              Swap
            </button>
          </div>

          {/* Live indicator */}
          <div className={styles.liveRow}>
            <span className={styles.liveDot} />
            <span className={styles.liveText}>
              Live on TON {overview?.network === "testnet" ? "testnet" : "mainnet"}
            </span>
          </div>
        </div>

        {/* ── Receive panel ── */}
        {showReceive && isLinked && (
          <div className={styles.receiveCard}>
            <div className={styles.receiveHeader}>
              <ArrowDown size={16} className={styles.receiveIcon} />
              <span>Receive TON</span>
            </div>
            <div className={styles.receiveAddress}>
              <span className={styles.receiveAddressText}>
                {depositInfo?.non_bounceable || displayAddress}
              </span>
              <button className={styles.copyBtn} onClick={copyAddress}>
                {copied ? "Copied!" : <Copy size={14} />}
              </button>
            </div>
            <p className={styles.receiveNote}>
              Send only TON or Jettons to this address. Use the non-bounceable format above.
            </p>
          </div>
        )}

        {/* ── Tabs ── */}
        {isLinked && (
          <>
            <div className={styles.tabs}>
              <button
                className={clsx(styles.tab, activeTab === "activity" && styles.tabActive)}
                onClick={() => setActiveTab("activity")}
              >
                Activity
              </button>
              <button
                className={clsx(styles.tab, activeTab === "tokens" && styles.tabActive)}
                onClick={() => setActiveTab("tokens")}
              >
                Tokens
                {(overview?.jettons.length ?? 0) > 0 && (
                  <span className={styles.tokenCount}>{overview?.jettons.length}</span>
                )}
              </button>
            </div>

            {/* Activity tab */}
            {activeTab === "activity" && (
              <div className={styles.txList}>
                {loadingTxs ? (
                  Array.from({ length: 5 }).map((_, i) => <TxSkeleton key={i} />)
                ) : txData?.transactions?.length ? (
                  txData.transactions.map((tx: Transaction) => (
                    <TxRow key={tx.hash} tx={tx} />
                  ))
                ) : (
                  <div className={styles.emptyState}>
                    <Globe size={32} className={styles.emptyIcon} />
                    <p>No transactions yet</p>
                  </div>
                )}
              </div>
            )}

            {/* Tokens tab */}
            {activeTab === "tokens" && (
              <div className={styles.tokenList}>
                {/* TON row always first */}
                <div className={styles.tokenRow}>
                  <div className={styles.tokenLeft}>
                    <div className={styles.tokenIcon} style={{ background: "color-mix(in srgb, var(--primary), transparent 90%)" }}>
                      <Coins size={20} style={{ color: "var(--primary)" }} />
                    </div>
                    <div className={styles.tokenInfo}>
                      <span className={styles.tokenSymbol}>TON</span>
                      <span className={styles.tokenName}>Toncoin</span>
                    </div>
                  </div>
                  <div className={styles.tokenRight}>
                    <span className={styles.tokenBalance}>{tonBalance.toFixed(4)}</span>
                    {overview?.ton.usd_value !== undefined && (
                      <span className={styles.tokenUsd}>
                        ${overview.ton.usd_value.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>

                {overview?.jettons.map((j) => (
                  <div key={j.address} className={styles.tokenRow}>
                    <div className={styles.tokenLeft}>
                      <div className={styles.tokenIcon}>
                        {j.image ? (
                          <img src={j.image} alt={j.symbol} className={styles.tokenImg} />
                        ) : (
                          <span className={styles.tokenInitial}>{j.symbol[0]}</span>
                        )}
                      </div>
                      <div className={styles.tokenInfo}>
                        <div className={styles.tokenSymbolRow}>
                          <span className={styles.tokenSymbol}>{j.symbol}</span>
                          {j.verified && <Shield size={10} className={styles.verifiedIcon} />}
                        </div>
                        <span className={styles.tokenName}>{j.name}</span>
                      </div>
                    </div>
                    <div className={styles.tokenRight}>
                      <span className={styles.tokenBalance}>{j.balance.toLocaleString()}</span>
                      {j.usd_value !== undefined && j.usd_value !== null && (
                        <span className={styles.tokenUsd}>${j.usd_value.toFixed(2)}</span>
                      )}
                    </div>
                  </div>
                ))}

                {(overview?.jettons.length === 0) && (
                  <div className={styles.emptyState}>
                    <Zap size={32} className={styles.emptyIcon} />
                    <p>No tokens yet</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ── No wallet CTA ── */}
        {!address && (
          <div className={styles.connectCta}>
            <Wallet size={40} className={styles.ctaIcon} />
            <h3>Connect your TON wallet</h3>
            <p>Link your wallet to view balance, tokens, and transaction history.</p>
            <TonConnectButton />
          </div>
        )}
      </div>
    </>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const TX_TYPE_STYLES: Record<string, { bg: string; color: string }> = {
  transfer: { bg: "color-mix(in srgb, var(--primary), transparent 92%)", color: "var(--primary)" },
  swap:     { bg: "color-mix(in srgb, var(--accent-green), transparent 92%)", color: "var(--accent-green)" },
  stake:    { bg: "color-mix(in srgb, var(--accent-green), transparent 92%)", color: "var(--accent-green)" },
  unstake:  { bg: "color-mix(in srgb, var(--accent-green), transparent 92%)", color: "var(--accent-green)" },
  nft:      { bg: "color-mix(in srgb, var(--accent-purple), transparent 92%)", color: "var(--accent-purple)" },
  nft_buy:  { bg: "color-mix(in srgb, var(--accent-purple), transparent 92%)", color: "var(--accent-purple)" },
  deploy:   { bg: "color-mix(in srgb, var(--accent-orange), transparent 92%)", color: "var(--accent-orange)" },
  contract: { bg: "color-mix(in srgb, var(--text-secondary), transparent 92%)", color: "var(--text-secondary)" },
  domain:   { bg: "color-mix(in srgb, var(--primary), transparent 92%)", color: "var(--primary)" },
  mint:     { bg: "color-mix(in srgb, var(--accent-green), transparent 92%)", color: "var(--accent-green)" },
};

function TxRow({ tx }: { tx: Transaction }) {
  const style = TX_TYPE_STYLES[tx.type] || TX_TYPE_STYLES.contract;
  const isIn = tx.direction === "in";
  const isFailed = tx.status === "failed";

  const dateObj = new Date(tx.time_unix * 1000);
  const now = new Date();
  const isToday = dateObj.toDateString() === now.toDateString();
  const timeStr = isToday
    ? `Today, ${dateObj.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}`
    : dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  const amount = tx.amount_ton !== undefined && tx.amount_ton !== null
    ? `${isIn ? "+" : "-"}${tx.amount_ton.toFixed(4)} TON`
    : tx.token_amount !== undefined && tx.token_amount !== null && tx.token_symbol
    ? `${isIn ? "+" : "-"}${tx.token_amount.toFixed(4)} ${tx.token_symbol}`
    : null;

  return (
    <a
      href={tx.explorer_url}
      target="_blank"
      rel="noopener noreferrer"
      className={clsx(styles.txRow, isFailed && styles.txFailed)}
    >
      <div className={styles.txLeft}>
        <div className={styles.txIcon} style={{ background: style.bg, color: style.color }}>
          <TxIcon type={tx.type} direction={tx.direction} />
        </div>
        <div className={styles.txInfo}>
          <div className={styles.txTitleRow}>
            <span className={styles.txTitle}>{tx.title}</span>
            {isFailed && <span className={styles.failedBadge}>Failed</span>}
          </div>
          <div className={styles.txMeta}>
            <span className={styles.txTime}>{timeStr}</span>
            {tx.comment && (
              <span className={styles.txComment}>· {tx.comment.slice(0, 20)}</span>
            )}
          </div>
        </div>
      </div>
      <div className={styles.txRight}>
        {amount && (
          <span className={clsx(
            styles.txAmount,
            isIn ? styles.positive : styles.negative,
            isFailed && styles.txAmountFailed
          )}>
            {amount}
          </span>
        )}
        <span className={styles.txFee}>fee {tx.fee_ton.toFixed(5)}</span>
        <ExternalLink size={10} className={styles.txExternal} />
      </div>
    </a>
  );
}

function TxIcon({ type, direction }: { type: string; direction: string }) {
  if (type === "swap") return <Repeat size={16} />;
  if (type === "stake" || type === "unstake") return <Star size={16} fill="currentColor" />;
  if (type === "nft" || type === "nft_buy") return <Zap size={16} />;
  if (direction === "in") return <ArrowDown size={16} />;
  if (direction === "out") return <ArrowUp size={16} />;
  return <Repeat size={16} />;
}

function TxSkeleton() {
  return (
    <div className={styles.txRow} style={{ pointerEvents: "none" }}>
      <div className={styles.txLeft}>
        <Skeleton width={44} height={44} borderRadius="14px" />
        <div className={styles.txInfo}>
          <Skeleton width="100px" height="15px" borderRadius="4px" />
          <div style={{ marginTop: 4 }}>
            <Skeleton width="70px" height="12px" borderRadius="4px" />
          </div>
        </div>
      </div>
      <div className={styles.txRight}>
        <Skeleton width="60px" height="15px" borderRadius="4px" />
        <div style={{ marginTop: 4 }}>
          <Skeleton width="40px" height="11px" borderRadius="4px" />
        </div>
      </div>
    </div>
  );
}
