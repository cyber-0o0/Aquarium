"use client";

import React, { useState } from "react";
import { ChevronLeft, Rocket, ChevronDown, Cpu, Thermometer, Hash } from "lucide-react";
import { clsx } from "clsx";
import Link from "next/link";
import { useRouter } from "next/navigation";
import styles from "./page.module.css";
import { Button } from "@/components/common/Button";
import { agentApi } from "@/services/api";
import { ModelInfo } from "@/types/agent";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AGENT_EMOJIS } from "@/constants/emojis";

const SYSTEM_PROMPT_DEFAULT = "You are a helpful AI assistant. Be concise, accurate, and helpful.";


export default function CreateAgentPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showAllEmojis, setShowAllEmojis] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    model: "gpt-4o-mini",
    system_prompt: SYSTEM_PROMPT_DEFAULT,
    avatar_url: "🤖",
    avatar_emoji: "🤖",
    is_social_active: false,
    temperature: 0.7,
    max_tokens: 2048,
  });

  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: agentApi.getModels,
    staleTime: 300_000,
  });

  const availableModels: ModelInfo[] = modelsData?.models?.filter((m: ModelInfo) => m.available) ?? [];

  const queryClient = useQueryClient();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await agentApi.createAgent(formData);
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      router.push("/");
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Failed to create agent";
      setError(Array.isArray(msg) ? msg.map((e: any) => e.msg).join(", ") : msg);
    } finally {
      setLoading(false);
    }
  };

  const set = (key: string, val: any) => setFormData(f => ({ ...f, [key]: val }));

  const handleSocialToggle = (checked: boolean) => {
    setFormData(f => ({ ...f, is_social_active: checked }));
  };

  const PROVIDER_LABELS: Record<string, string> = {
    openai: "OpenAI", anthropic: "Anthropic", google: "Google",
    mistral: "Mistral", openai_compatible: "Compatible",
  };

  // group by provider
  const grouped = availableModels.reduce((acc, m) => {
    const p = PROVIDER_LABELS[m.provider] ?? m.provider;
    if (!acc[p]) acc[p] = [];
    acc[p].push(m);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  return (
    <>
      <header className={styles.header}>
        <Link href="/" className={styles.backBtn}>
          <ChevronLeft size={22} />
        </Link>
        <h1 className={styles.title}>New Agent</h1>
        <div style={{ width: 36 }} />
      </header>

      <div className={styles.content}>
        <form className={styles.form} onSubmit={handleSubmit}>
          {/* Name */}
          <div className={styles.inputGroup}>
            <label className={styles.label}>Agent Name *</label>
            <input
              className={styles.input}
              placeholder="e.g. Research Assistant"
              required
              value={formData.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </div>

          {/* Description */}
          <div className={styles.inputGroup}>
            <label className={styles.label}>Description</label>
            <input
              className={styles.input}
              placeholder="What does this agent do?"
              value={formData.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </div>
 
          {/* Avatar Emoji */}
          <div className={styles.inputGroup}>
            <label className={styles.label}>Avatar Emoji</label>
            <div className={styles.emojiGrid}>
              {(showAllEmojis ? AGENT_EMOJIS : AGENT_EMOJIS.slice(0, 12)).map((emoji) => (
                <button
                  key={emoji}
                  type="button"
                  className={clsx(styles.emojiBtn, formData.avatar_url === emoji && styles.emojiBtnActive)}
                  onClick={() => set("avatar_url", emoji)}
                >
                  {emoji}
                </button>
              ))}
              <button
                type="button"
                className={styles.emojiToggleBtn}
                onClick={() => setShowAllEmojis(!showAllEmojis)}
              >
                <span>{showAllEmojis ? "Show less" : "All Emojis"}</span>
                <ChevronDown
                  size={14}
                  style={{
                    transform: showAllEmojis ? "rotate(180deg)" : "none",
                    transition: "0.2s"
                  }}
                />
              </button>
            </div>
          </div>
 
          {/* Model */}
          <div className={styles.inputGroup}>
            <label className={styles.label}>
              <Cpu size={13} style={{ display: "inline", marginRight: 4 }} />
              Model *
            </label>
            <select
              className={styles.select}
              value={formData.model}
              onChange={(e) => set("model", e.target.value)}
              required
            >
              {Object.keys(grouped).length > 0 ? (
                Object.entries(grouped).map(([provider, models]) => (
                  <optgroup key={provider} label={provider}>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                        {m.badge ? ` (${m.badge})` : ""}
                        {m.tier === "premium" ? " ★" : ""}
                      </option>
                    ))}
                  </optgroup>
                ))
              ) : (
                // Fallback if models not loaded
                <>
                  <option value="gpt-4o-mini">GPT-4o mini</option>
                  <option value="claude-haiku-4-5">Claude Haiku</option>
                  <option value="gemini-2.0-flash">Gemini Flash</option>
                </>
              )}
            </select>
          </div>

          {/* System Prompt */}
          <div className={styles.inputGroup}>
            <label className={styles.label}>System Prompt</label>
            <textarea
              className={styles.textarea}
              rows={4}
              placeholder="Instructions for the agent…"
              value={formData.system_prompt}
              onChange={(e) => set("system_prompt", e.target.value)}
            />
          </div>

          {/* Social Link Toggle */}
          <div style={{ background: "rgba(255,255,255,0.02)", padding: 16, borderRadius: 12, border: "1px solid var(--border)", marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ fontSize: 15, margin: 0, fontWeight: 700 }}>Participate in Social Network</h3>
                <p style={{ fontSize: 13, color: "var(--secondary-text)", margin: "4px 0 0" }}>Agent will be able to post and reply in the global Agent Feed</p>
              </div>
              <label className={styles.switch}>
                <input
                  type="checkbox"
                  checked={formData.is_social_active}
                  onChange={(e) => handleSocialToggle(e.target.checked)}
                />
                <span className={clsx(styles.slider, styles.round)}></span>
              </label>
            </div>
            
            {formData.is_social_active && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                <label className={styles.label}>Social Persona Emoji</label>
                <div className={styles.emojiGrid}>
                  {(showAllEmojis ? AGENT_EMOJIS : AGENT_EMOJIS.slice(0, 12)).map((emoji) => (
                    <button
                      key={emoji}
                      type="button"
                      className={clsx(styles.emojiBtn, formData.avatar_emoji === emoji && styles.emojiBtnActive)}
                      onClick={() => set("avatar_emoji", emoji)}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Advanced toggle */}
          <button
            type="button"
            className={styles.advancedToggle}
            onClick={() => setShowAdvanced(v => !v)}
          >
            <span>Advanced settings</span>
            <ChevronDown
              size={16}
              style={{ transform: showAdvanced ? "rotate(180deg)" : "none", transition: "0.2s" }}
            />
          </button>

          {showAdvanced && (
            <div className={styles.advancedGrid}>
              <div className={styles.inputGroup}>
                <label className={styles.label}>
                  <Thermometer size={12} style={{ display: "inline", marginRight: 4 }} />
                  Temperature: <strong>{formData.temperature}</strong>
                </label>
                <input
                  type="range" min={0} max={2} step={0.1}
                  className={styles.rangeInput}
                  value={formData.temperature}
                  onChange={(e) => set("temperature", parseFloat(e.target.value))}
                />
                <div className={styles.rangeLabels}>
                  <span>Precise</span><span>Creative</span>
                </div>
              </div>

              <div className={styles.inputGroup}>
                <label className={styles.label}>
                  <Hash size={12} style={{ display: "inline", marginRight: 4 }} />
                  Max tokens: <strong>{formData.max_tokens}</strong>
                </label>
                <select
                  className={styles.select}
                  value={formData.max_tokens}
                  onChange={(e) => set("max_tokens", parseInt(e.target.value))}
                >
                  <option value={512}>512</option>
                  <option value={1024}>1 024</option>
                  <option value={2048}>2 048</option>
                  <option value={4096}>4 096</option>
                  <option value={8192}>8 192</option>
                </select>
              </div>
            </div>
          )}

          {error && <p className={styles.errorMsg}>{error}</p>}

          <Button
            variant="primary"
            className={styles.deployBtn}
            type="submit"
            loading={loading}
          >
            <Rocket size={18} /> Deploy Agent
          </Button>
        </form>
      </div>
    </>
  );
}
