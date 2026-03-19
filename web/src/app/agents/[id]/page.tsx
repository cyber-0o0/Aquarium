"use client";

import React, { useState } from "react";
import {
  ChevronLeft, Play, Pause, Terminal, Cpu, Zap,
  RotateCcw, Clock, CheckCircle2, XCircle, Loader2,
  Settings2, Hash, MessageSquare
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import styles from "./page.module.css";
import { clsx } from "clsx";
import { Button } from "@/components/common/Button";
import { Skeleton } from "@/components/common/Skeleton";
import { agentApi } from "@/services/api";
import { Agent, Task, RunResult } from "@/types/agent";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const STATUS_COLOR: Record<string, string> = {
  active: "var(--status-active)",
  idle:   "var(--status-idle)",
  error:  "var(--status-error)",
  paused: "var(--secondary-text)",
};

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const [taskInput, setTaskInput] = useState("");
  const [lastResult, setLastResult] = useState<RunResult | null>(null);

  const { data: agent, isLoading } = useQuery<Agent>({
    queryKey: ["agent", id],
    queryFn: () => agentApi.getAgent(id),
    refetchInterval: 10_000,
  });

  const { data: tasks = [], isLoading: loadingTasks } = useQuery<Task[]>({
    queryKey: ["agent-tasks", id],
    queryFn: () => agentApi.getAgentTasks(id),
    staleTime: 15_000,
  });

  const [runError, setRunError] = useState<string | null>(null);

  const runMutation = useMutation({
    mutationFn: (input: string) => agentApi.runAgent(id, input),
    onSuccess: (data) => {
      setLastResult(data);
      setRunError(null);
      setTaskInput("");
      qc.invalidateQueries({ queryKey: ["agent-tasks", id] });
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail ??
        err?.message ??
        "Execution failed";
      setRunError(String(msg));
      // Refresh task list to show the failed task
      qc.invalidateQueries({ queryKey: ["agent-tasks", id] });
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
  });

  const initials = agent
    ? agent.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
    : "??";

  if (isLoading) return <LoadingSkeleton />;
  if (!agent) return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--secondary-text)" }}>
      Agent not found.{" "}
      <Link href="/" style={{ color: "var(--primary)" }}>Go back</Link>
    </div>
  );

  const MODEL_LABEL: Record<string, string> = {
    "gpt-4o": "GPT-4o", "gpt-4o-mini": "GPT-4o mini",
    "claude-sonnet-4-5": "Claude Sonnet", "claude-haiku-4-5": "Claude Haiku",
    "claude-opus-4-5": "Claude Opus", "gemini-2.0-flash": "Gemini Flash",
  };
  const modelLabel = MODEL_LABEL[agent.model] ?? agent.model;

  return (
    <>
      <header className={styles.header}>
        <Link href="/" className={styles.backBtn}>
          <ChevronLeft size={22} />
        </Link>
        <h1 className={styles.headerTitle}>{agent.name}</h1>
        <Link href={`/agents/${id}/edit`} className={styles.editBtn}>
          <Settings2 size={18} />
        </Link>
      </header>

      <div className={styles.content}>
        {/* ── Hero ── */}
        <div className={styles.heroCard}>
          <div className={styles.heroTop}>
            <div className={styles.heroAvatar} style={{ borderColor: `${STATUS_COLOR[agent.status]}44` }}>
              {agent.avatar_url ? (
                <span className={styles.heroInitials} style={{ fontSize: 40 }}>{agent.avatar_url}</span>
              ) : (
                <span className={styles.heroInitials}>{initials}</span>
              )}
              <span className={styles.heroDot} style={{ background: STATUS_COLOR[agent.status] }} />
            </div>
            <div className={styles.heroMeta}>
              <h2 className={styles.heroName}>{agent.name}</h2>
              {agent.description && <p className={styles.heroDesc}>{agent.description}</p>}
              <div className={styles.heroTags}>
                <span className={styles.modelTag}><Cpu size={11}/> {modelLabel}</span>
                <span className={clsx(styles.statusTag, styles[`status_${agent.status}`])}>
                  ● {agent.status}
                </span>
              </div>
            </div>
          </div>

          <div className={styles.actionRow}>
            <Button
              variant="primary"
              className={styles.runBtn}
              onClick={() => {
                if (agent.bot_username && agent.tg_thread_id) {
                  let url = "";
                  
                  if (agent.tg_group_id && agent.tg_group_id.startsWith("-100")) {
                    // Групповой топик
                    const groupId = agent.tg_group_id.substring(4);
                    url = `https://t.me/c/${groupId}/${agent.tg_thread_id}`;
                  } else {
                    // Личный топик в боте (Telegram 11+)
                    url = `https://t.me/${agent.bot_username}/${agent.tg_thread_id}`;
                  }
                  
                  if ((window as any).Telegram?.WebApp) {
                    (window as any).Telegram.WebApp.openTelegramLink(url);
                  } else {
                    window.open(url, "_blank");
                  }
                } else if (agent.bot_username) {
                  // Основной чат бота
                  const url = `https://t.me/${agent.bot_username}`;
                  if ((window as any).Telegram?.WebApp) {
                    (window as any).Telegram.WebApp.openTelegramLink(url);
                  } else {
                    window.open(url, "_blank");
                  }
                } else {
                  window.open("https://t.me/StrategyClaw_bot", "_blank");
                }
              }}
            >
              <MessageSquare size={16} /> Open in Chat
            </Button>
          </div>
        </div>

        {/* ── Run Task panel ── */}
        {/* ── Chat panel removed (moved to Telegram) ── */}

        {/* ── Last result ── */}
        {lastResult && (
          <div className={styles.resultCard}>
            <div className={styles.resultHeader}>
              <CheckCircle2 size={16} className={styles.resultIcon} />
              <span>Last result</span>
              <span className={styles.resultTokens}>{lastResult.tokens_used} tokens</span>
            </div>
            <p className={styles.resultText}>{lastResult.output}</p>
            {lastResult.tools_used.length > 0 && (
              <div className={styles.toolsUsed}>
                {lastResult.tools_used.map((t) => (
                  <span key={t} className={styles.toolChip}><Zap size={10}/> {t}</span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Stats ── */}
        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <Hash size={14} className={styles.statIcon} />
            <span className={styles.statVal}>{tasks.length}</span>
            <span className={styles.statLabel}>Total tasks</span>
          </div>
          <div className={styles.statCard}>
            <CheckCircle2 size={14} className={styles.statIcon} />
            <span className={styles.statVal}>
              {tasks.filter(t => t.status === 'success').length}
            </span>
            <span className={styles.statLabel}>Successful</span>
          </div>
          <div className={styles.statCard}>
            <MessageSquare size={14} className={styles.statIcon} />
            <span className={styles.statVal}>
              {tasks.reduce((sum, t) => sum + (t.tokens_used || 0), 0).toLocaleString()}
            </span>
            <span className={styles.statLabel}>Tokens</span>
          </div>
        </div>

        {/* ── Config summary ── */}
        <div className={styles.configCard}>
          <h3 className={styles.sectionLabel}>Configuration</h3>
          <div className={styles.configGrid}>
            <ConfigRow label="Model" value={modelLabel} />
            <ConfigRow label="Temperature" value={agent.temperature.toFixed(1)} />
            <ConfigRow label="Max tokens" value={agent.max_tokens.toLocaleString()} />
            <ConfigRow label="Schedule" value={agent.schedule_type} />
            {agent.scenario && <ConfigRow label="Scenario" value="Configured" accent />}
          </div>
        </div>

        {/* ── Task history ── */}
        <div className={styles.historySection}>
          <h3 className={styles.sectionLabel}>Task History</h3>
          <div className={styles.taskList}>
            {loadingTasks ? (
              Array.from({ length: 3 }).map((_, i) => <TaskRowSkeleton key={i} />)
            ) : tasks.length > 0 ? (
              tasks.map((task) => <TaskRow key={task.id} task={task} />)
            ) : (
              <div className={styles.emptyTasks}>
                <Terminal size={28} className={styles.emptyIcon} />
                <p>No tasks yet — run one above</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function ConfigRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={styles.configRow}>
      <span className={styles.configLabel}>{label}</span>
      <span className={clsx(styles.configValue, accent && styles.configAccent)}>{value}</span>
    </div>
  );
}

function TaskRow({ task }: { task: Task }) {
  const icons = {
    success: <CheckCircle2 size={14} style={{ color: "var(--status-active)" }} />,
    failed:  <XCircle size={14} style={{ color: "var(--status-error)" }} />,
    running: <Loader2 size={14} style={{ color: "var(--status-idle)", animation: "spin 1s linear infinite" }} />,
    queued:  <Clock size={14} style={{ color: "var(--secondary-text)" }} />,
    cancelled: <XCircle size={14} style={{ color: "var(--secondary-text)" }} />,
  };
  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    return `${Math.floor(diff / 3_600_000)}h ago`;
  };

  const input = task.input_data?.input ?? "—";

  return (
    <div className={styles.taskRow}>
      <div className={styles.taskLeft}>
        {icons[task.status] ?? icons.queued}
        <div className={styles.taskInfo}>
          <span className={styles.taskInput}>{String(input).slice(0, 60)}{String(input).length > 60 ? "…" : ""}</span>
          <span className={styles.taskTime}>{timeAgo(task.created_at)}</span>
        </div>
      </div>
      {task.tokens_used > 0 && (
        <span className={styles.taskTokens}>{task.tokens_used.toLocaleString()} tk</span>
      )}
    </div>
  );
}

function TaskRowSkeleton() {
  return (
    <div className={styles.taskRow}>
      <div className={styles.taskLeft}>
        <Skeleton width={14} height={14} borderRadius="50%" />
        <div className={styles.taskInfo}>
          <Skeleton width="60%" height="14px" borderRadius="4px" />
          <Skeleton width="40px" height="11px" borderRadius="4px" />
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <>
      <header style={{ padding: "48px 24px 20px", display: "flex", alignItems: "center", gap: 12 }}>
        <Skeleton width={32} height={32} borderRadius="50%" />
        <Skeleton width="120px" height="24px" borderRadius="6px" />
      </header>
      <div style={{ padding: "0 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        <Skeleton width="100%" height="140px" borderRadius="20px" />
        <Skeleton width="100%" height="80px" borderRadius="16px" />
      </div>
    </>
  );
}
