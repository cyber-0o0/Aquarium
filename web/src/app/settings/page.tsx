"use client";

import React, { useState } from "react";
import {
  User, Wallet, Key, ChevronRight, LogOut,
  Shield, Bell, Trash2, Plus, Check, X, Eye, EyeOff,
  Copy, ExternalLink, Cpu
} from "lucide-react";
import styles from "./page.module.css";
import { clsx } from "clsx";
import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";
import { apiKeysApi, agentApi } from "@/services/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Agent } from "@/types/agent";

const PROVIDER_COLORS: Record<string, string> = {
  openai: "#10A37F", anthropic: "#D4A017", google: "#4285F4",
  mistral: "#FF7000", openai_compatible: "#8B5CF6",
};
const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI", anthropic: "Anthropic", google: "Google / Gemini",
  mistral: "Mistral AI", openai_compatible: "Custom / Compatible",
};

const ACCENT_COLORS = [
  { name: "Lime", value: "#C8FF44" },
  { name: "Cyan", value: "#00E0FF" },
  { name: "Purple", value: "#A855F7" },
  { name: "Orange", value: "#F97316" },
  { name: "Pink", value: "#EC4899" },
  { name: "Blue", value: "#3B82F6" },
];

export default function SettingsPage() {
  const { user, accessToken, clearAuth } = useAuthStore();
  const { theme, setTheme, accentColor, setAccentColor } = useUIStore();
  const qc = useQueryClient();

  const [showAddKey, setShowAddKey] = useState(false);
  const [newKey, setNewKey] = useState({ provider: "openai", api_key: "", label: "" });
  const [showKeyValue, setShowKeyValue] = useState<Record<string, boolean>>({});

  const { data: agents = [] } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: agentApi.getAgents,
    enabled: !!accessToken,
    staleTime: 30_000,
  });

  const { data: apiKeys = [], isLoading: keysLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: apiKeysApi.list,
    enabled: !!accessToken,
    staleTime: 60_000,
  });

  const addKeyMutation = useMutation({
    mutationFn: () => apiKeysApi.add({
      provider: newKey.provider,
      api_key: newKey.api_key,
      label: newKey.label || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      setShowAddKey(false);
      setNewKey({ provider: "openai", api_key: "", label: "" });
    },
  });

  const deleteKeyMutation = useMutation({
    mutationFn: (keyId: string) => apiKeysApi.delete(keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  const verifyKeyMutation = useMutation({
    mutationFn: (keyId: string) => apiKeysApi.verify(keyId),
  });

  if (!accessToken) {
    return (
      <div style={{ padding: "60px 24px", textAlign: "center", color: "var(--secondary-text)" }}>
        <p style={{ fontSize: 16, marginBottom: 8 }}>Not authenticated</p>
        <p style={{ fontSize: 13 }}>Open the app via Telegram</p>
      </div>
    );
  }

  const initials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : user?.first_name
    ? user.first_name.slice(0, 2).toUpperCase()
    : "??";

  const displayName = user?.first_name
    ? `${user.first_name}${user.last_name ? " " + user.last_name : ""}`
    : user?.username ?? "Anonymous";

  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
      </header>

      <div className={styles.content}>
        {/* ── Profile ── */}
        <div className={styles.profileCard}>
          <div className={styles.profileAvatar}>{initials}</div>
          <div className={styles.profileInfo}>
            <span className={styles.profileName}>{displayName}</span>
            {user?.username && (
              <span className={styles.profileHandle}>@{user.username}</span>
            )}
            <div className={styles.planBadge}>
              <span>⭐</span>
              <span style={{ textTransform: "capitalize" }}>{user?.plan ?? "free"}</span> Plan
            </div>
          </div>
        </div>

        {/* ── Stats ── */}
        <div className={styles.statsRow}>
          <div className={styles.statItem}>
            <span className={styles.statVal}>{agents.length}</span>
            <span className={styles.statLabel}>Agents</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statVal}>{apiKeys.length}</span>
            <span className={styles.statLabel}>API keys</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statVal}>{user?.wallet_address ? "Linked" : "—"}</span>
            <span className={styles.statLabel}>Wallet</span>
          </div>
        </div>

        {/* ── Wallet info ── */}
        {user?.wallet_address && (
          <div className={styles.section}>
            <h2 className={styles.sectionHeader}>Wallet</h2>
            <div className={styles.walletRow}>
              <Wallet size={16} style={{ color: "var(--primary)", flexShrink: 0 }} />
              <span className={styles.walletAddr}>
                {user.wallet_address.slice(0, 8)}…{user.wallet_address.slice(-6)}
              </span>
              <button
                className={styles.iconAction}
                onClick={() => navigator.clipboard.writeText(user.wallet_address!)}
              >
                <Copy size={14} />
              </button>
              <a
                href={`https://tonviewer.com/${user.wallet_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.iconAction}
              >
                <ExternalLink size={14} />
              </a>
            </div>
          </div>
        )}
        
        {/* ── Appearance ── */}
        <div className={styles.section}>
          <h2 className={styles.sectionHeader}>Appearance</h2>
          
          <div className={styles.appearanceGrid}>
            <div className={styles.appearanceItem}>
              <span className={styles.appearanceLabel}>Theme</span>
              <div className={styles.themeToggle}>
                <button 
                  className={clsx(styles.themeBtn, theme === 'system' && styles.activeTheme)}
                  onClick={() => setTheme('system')}
                >
                  System
                </button>
                <button 
                  className={clsx(styles.themeBtn, theme === 'dark' && styles.activeTheme)}
                  onClick={() => setTheme('dark')}
                >
                  Dark
                </button>
                <button 
                  className={clsx(styles.themeBtn, theme === 'light' && styles.activeTheme)}
                  onClick={() => setTheme('light')}
                >
                  Light
                </button>
              </div>
            </div>

            <div className={styles.appearanceItem}>
              <span className={styles.appearanceLabel}>Accent Color</span>
              <div className={styles.colorGrid}>
                {ACCENT_COLORS.map((color) => (
                  <button
                    key={color.value}
                    className={clsx(styles.colorCircle, accentColor === color.value && styles.activeColor)}
                    style={{ backgroundColor: color.value }}
                    onClick={() => setAccentColor(color.value)}
                    title={color.name}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── API Keys ── */}
        <div className={styles.section}>
          <div className={styles.sectionHeaderRow}>
            <h2 className={styles.sectionHeader}>API Keys</h2>
            <button className={styles.addBtn} onClick={() => setShowAddKey(v => !v)}>
              <Plus size={14} /> Add
            </button>
          </div>

          <p className={styles.sectionNote}>
            Your own keys take priority over platform keys for any model.
          </p>

          {showAddKey && (
            <div className={styles.addKeyForm}>
              <select
                className={styles.select}
                value={newKey.provider}
                onChange={(e) => setNewKey(k => ({ ...k, provider: e.target.value }))}
              >
                {Object.entries(PROVIDER_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
              <input
                className={styles.input}
                placeholder="API key"
                type="password"
                value={newKey.api_key}
                onChange={(e) => setNewKey(k => ({ ...k, api_key: e.target.value }))}
              />
              <input
                className={styles.input}
                placeholder="Label (optional)"
                value={newKey.label}
                onChange={(e) => setNewKey(k => ({ ...k, label: e.target.value }))}
              />
              {addKeyMutation.isError && (
                <p className={styles.errorMsg}>
                  {(addKeyMutation.error as any)?.response?.data?.detail ?? "Failed to save key"}
                </p>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className={clsx(styles.saveBtn)}
                  onClick={() => newKey.api_key && addKeyMutation.mutate()}
                  disabled={!newKey.api_key || addKeyMutation.isPending}
                >
                  {addKeyMutation.isPending ? "Saving…" : "Save key"}
                </button>
                <button className={styles.cancelBtn} onClick={() => setShowAddKey(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className={styles.keysList}>
            {keysLoading ? (
              <div className={styles.keysEmpty}>Loading…</div>
            ) : apiKeys.length === 0 ? (
              <div className={styles.keysEmpty}>
                <Cpu size={28} style={{ opacity: 0.25 }} />
                <p>No custom API keys yet</p>
                <p style={{ fontSize: 12 }}>Platform keys will be used by default</p>
              </div>
            ) : (
              apiKeys.map((key: any) => (
                <div key={key.id} className={styles.keyRow}>
                  <div
                    className={styles.keyProviderDot}
                    style={{ background: PROVIDER_COLORS[key.provider] ?? "#888" }}
                  />
                  <div className={styles.keyInfo}>
                    <span className={styles.keyLabel}>{key.label ?? PROVIDER_LABELS[key.provider] ?? key.provider}</span>
                    <span className={styles.keyHint}>…{key.key_hint}</span>
                  </div>
                  <div className={styles.keyActions}>
                    <button
                      className={styles.iconAction}
                      onClick={() => verifyKeyMutation.mutate(key.id)}
                      title="Verify key"
                    >
                      {verifyKeyMutation.isPending ? "…" : <Check size={13} />}
                    </button>
                    <button
                      className={clsx(styles.iconAction, styles.deleteAction)}
                      onClick={() => deleteKeyMutation.mutate(key.id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Danger ── */}
        <div className={styles.section}>
          <h2 className={styles.sectionHeader}>Session</h2>
          <button className={styles.logoutBtn} onClick={clearAuth}>
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </div>
    </>
  );
}
