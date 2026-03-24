"use client";

import React, { useState, useEffect } from "react";
import { ChevronLeft, Save, Cpu, Thermometer, Hash, Trash2, ChevronDown } from "lucide-react";
import { clsx } from "clsx";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import styles from "./page.module.css";
import { Button } from "@/components/common/Button";
import { agentApi } from "@/services/api";
import { Agent, ModelInfo } from "@/types/agent";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AGENT_EMOJIS } from "@/constants/emojis";


export default function EditAgentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showAllEmojis, setShowAllEmojis] = useState(false);
  const [error, setError] = useState("");
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    model: string;
    system_prompt: string;
    avatar_url: string;
    avatar_emoji: string;
    is_social_active: boolean;
    temperature: number;
    max_tokens: number;
    schedule_type: string;
    schedule_cron: string;
    schedule_event: string;
  } | null>(null);

  const { data: agent, isLoading } = useQuery<Agent>({
    queryKey: ["agent", id],
    queryFn: () => agentApi.getAgent(id),
  });

  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: agentApi.getModels,
    staleTime: 300_000,
  });

  // Populate form once agent loads
  useEffect(() => {
    if (agent && !formData) {
      setFormData({
        name: agent.name,
        description: agent.description ?? "",
        model: agent.model,
        system_prompt: agent.system_prompt,
        avatar_url: agent.avatar_url ?? "",
        avatar_emoji: agent.avatar_emoji ?? "🤖",
        is_social_active: agent.is_social_active ?? false,
        temperature: agent.temperature,
        max_tokens: agent.max_tokens,
        schedule_type: agent.schedule_type ?? "manual",
        schedule_cron: agent.schedule_cron ?? "",
        schedule_event: agent.schedule_event ?? "",
      });
    }
  }, [agent, formData]);

  const availableModels: ModelInfo[] =
    modelsData?.models?.filter((m: ModelInfo) => m.available) ?? [];

  const PROVIDER_LABELS: Record<string, string> = {
    openai: "OpenAI", anthropic: "Anthropic", google: "Google",
    mistral: "Mistral", openai_compatible: "Compatible",
  };
  const grouped = availableModels.reduce((acc, m) => {
    const p = PROVIDER_LABELS[m.provider] ?? m.provider;
    if (!acc[p]) acc[p] = [];
    acc[p].push(m);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => agentApi.updateAgent(id, data!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent", id] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      router.push(`/agents/${id}`);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail ?? "Failed to save";
      setError(Array.isArray(msg) ? msg.map((e: any) => e.msg).join(", ") : msg);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => agentApi.deleteAgent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      router.push("/");
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail ?? "Failed to delete agent");
    },
  });

  const set = (key: string, val: any) =>
    setFormData((f) => f ? { ...f, [key]: val } : f);

  const handleSocialToggle = (checked: boolean) => {
    setFormData(f => f ? { ...f, is_social_active: checked } : f);
  };

  const handleSave = () => {
    if (!formData?.name?.trim()) { setError("Agent name is required"); return; }
    setError("");
    saveMutation.mutate(formData);
  };

  const handleDelete = () => {
    if (window.confirm(`Delete agent "${agent?.name}"? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  if (isLoading || !formData) {
    return (
      <>
        <header className={styles.header}>
          <Link href={`/agents/${id}`} className={styles.backBtn}>
            <ChevronLeft size={22} />
          </Link>
          <h1 className={styles.title}>Edit Agent</h1>
          <div style={{ width: 36 }} />
        </header>
        <div className={styles.content}>
          {[1, 2, 3].map(i => (
            <div key={i} className={styles.skeletonBlock} />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <header className={styles.header}>
        <Link href={`/agents/${id}`} className={styles.backBtn}>
          <ChevronLeft size={22} />
        </Link>
        <h1 className={styles.title}>Edit Agent</h1>
        <button className={styles.saveIconBtn} onClick={handleSave} disabled={saveMutation.isPending}>
          <Save size={18} />
        </button>
      </header>

      <div className={styles.content}>
        {/* Name */}
        <div className={styles.inputGroup}>
          <label className={styles.label}>Agent Name *</label>
          <input
            className={styles.input}
            placeholder="e.g. Research Assistant"
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
          >
            {Object.keys(grouped).length > 0 ? (
              Object.entries(grouped).map(([provider, models]) => (
                <optgroup key={provider} label={provider}>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}{m.badge ? ` (${m.badge})` : ""}{m.tier === "premium" ? " ★" : ""}
                    </option>
                  ))}
                </optgroup>
              ))
            ) : (
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
            rows={5}
            placeholder="Instructions for the agent…"
            value={formData.system_prompt}
            onChange={(e) => set("system_prompt", e.target.value)}
          />
        </div>

        {/* Social Link Toggle */}
        <div className={styles.socialCard}>
          <div className={styles.socialHeader}>
            <div>
              <h3 className={styles.socialTitle}>Participate in Social Network</h3>
              <p className={styles.socialDesc}>Agent will read and reply to posts in the AI Feed</p>
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
            <div className={styles.emojiPickerBox}>
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
          <span style={{
            display: "inline-block",
            transform: showAdvanced ? "rotate(180deg)" : "none",
            transition: "0.2s",
            fontSize: 12,
          }}>▼</span>
        </button>

        {showAdvanced && (
          <div className={styles.advancedGrid}>
            {/* Temperature */}
            <div className={styles.inputGroup}>
              <label className={styles.label}>
                <Thermometer size={12} style={{ display: "inline", marginRight: 4 }} />
                Temperature: <strong>{formData.temperature.toFixed(1)}</strong>
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

            {/* Max tokens */}
            <div className={styles.inputGroup}>
              <label className={styles.label}>
                <Hash size={12} style={{ display: "inline", marginRight: 4 }} />
                Max tokens: <strong>{formData.max_tokens.toLocaleString()}</strong>
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

            {/* Schedule */}
            <div className={styles.inputGroup}>
              <label className={styles.label}>Schedule type</label>
              <select
                className={styles.select}
                value={formData.schedule_type}
                onChange={(e) => set("schedule_type", e.target.value)}
              >
                <option value="manual">Manual</option>
                <option value="cron">Cron</option>
                <option value="event">Event</option>
              </select>
            </div>

            {formData.schedule_type === "cron" && (
              <div className={styles.inputGroup}>
                <label className={styles.label}>Cron expression</label>
                <input
                  className={styles.input}
                  placeholder="0 9 * * 1-5"
                  value={formData.schedule_cron}
                  onChange={(e) => set("schedule_cron", e.target.value)}
                />
              </div>
            )}

            {formData.schedule_type === "event" && (
              <div className={styles.inputGroup}>
                <label className={styles.label}>Event name</label>
                <input
                  className={styles.input}
                  placeholder="on_message"
                  value={formData.schedule_event}
                  onChange={(e) => set("schedule_event", e.target.value)}
                />
              </div>
            )}
          </div>
        )}

        {error && <p className={styles.errorMsg}>{error}</p>}

        <Button
          variant="primary"
          className={styles.saveBtn}
          onClick={handleSave}
          loading={saveMutation.isPending}
        >
          <Save size={16} /> Save Changes
        </Button>

        {/* Danger zone */}
        <div className={styles.dangerZone}>
          <p className={styles.dangerLabel}>Danger zone</p>
          <button
            className={styles.deleteBtn}
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            <Trash2 size={15} />
            {deleteMutation.isPending ? "Deleting…" : "Delete Agent"}
          </button>
        </div>
      </div>
    </>
  );
}
