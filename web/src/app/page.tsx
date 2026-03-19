"use client";

import React from "react";
import { Agent } from "@/types/agent";
import { AgentCard } from "@/components/common/AgentCard";
import { AgentCardSkeleton } from "@/components/common/AgentCardSkeleton";
import { Button } from "@/components/common/Button";
import { Plus, Bell, Bot } from "lucide-react";
import Link from "next/link";
import styles from "./page.module.css";
import { agentApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useQuery } from "@tanstack/react-query";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function AgentsPage() {
  const { user, accessToken } = useAuthStore();

  const { data: agents = [], isLoading: loading } = useQuery({
    queryKey: ['agents'],
    queryFn: agentApi.getAgents,
    enabled: !!accessToken,
    staleTime: 30_000,
  });

  const activeCount = agents.filter((a: Agent) => a.status === 'active').length;
  const idleCount = agents.filter((a: Agent) => a.status === 'idle').length;

  // Display name: first_name > username > fallback
  const displayName = user?.first_name || user?.username || 'Agent';

  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.greeting}>{getGreeting()}</span>
          <h1 className={styles.title}>{displayName}'s Squad</h1>
        </div>
        <button className={styles.notifBtn} style={{ position: 'relative' }}>
          <Bell size={20} />
          <span className={styles.notifDot} />
        </button>
      </header>

      <div className={styles.statsRow}>
        <div className={styles.statChip}>
          <span className={styles.statDot} style={{ background: "var(--status-active)" }} />
          {activeCount} Active
        </div>
        <div className={styles.statChip}>
          <span className={styles.statDot} style={{ background: "var(--status-idle)" }} />
          {idleCount} Idle
        </div>
        <div className={styles.statChipMuted}>
          {loading ? '…' : agents.length} Total
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Your Squad</h2>
          <span className={styles.seeAll}>{agents.length} agents</span>
        </div>

        <div className={styles.agentList}>
          {loading ? (
            <>
              <AgentCardSkeleton />
              <AgentCardSkeleton />
              <AgentCardSkeleton />
            </>
          ) : agents.length > 0 ? (
            agents.map((agent: Agent) => (
              <Link key={agent.id} href={`/agents/${agent.id}`} style={{ textDecoration: 'none' }}>
                <AgentCard agent={agent} />
              </Link>
            ))
          ) : (
            <div className={styles.emptyState}>
              <Bot size={48} className={styles.emptyIcon} />
              <p className={styles.emptyTitle}>No agents yet</p>
              <p className={styles.emptyDesc}>Deploy your first AI agent to get started</p>
            </div>
          )}
        </div>

        <div className={styles.ctaArea}>
          <Link href="/create-agent" style={{ width: '100%' }}>
            <Button variant="primary" className={styles.deployBtn}>
              <Plus size={20} />
              Deploy New Agent
            </Button>
          </Link>
        </div>
      </div>
    </>
  );
}
