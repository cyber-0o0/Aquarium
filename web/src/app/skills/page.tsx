"use client";

import React, { useState } from "react";
import { Search, Check, Star, ChevronDown, Zap, Package, Trash2 } from "lucide-react";
import styles from "./page.module.css";
import { clsx } from "clsx";
import { Button } from "@/components/common/Button";
import { Skeleton } from "@/components/common/Skeleton";
import { skillsApi, agentApi } from "@/services/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Agent } from "@/types/agent";

const CATEGORIES = ["All", "search", "ton", "defi", "telegram", "utility", "data"];
const CAT_LABELS: Record<string, string> = {
  All: "All", search: "Search", ton: "TON", defi: "DeFi",
  telegram: "Telegram", utility: "Utility", data: "Data",
};

interface Skill {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  rating: number;
  installs: number;
  price_ton: string;
  color: string;
  review_status: string;
}

export default function SkillsPage() {
  const qc = useQueryClient();
  const [selectedCat, setSelectedCat] = useState("All");
  const [search, setSearch] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showAgentPicker, setShowAgentPicker] = useState(false);

  const { data: skills = [], isLoading } = useQuery<Skill[]>({
    queryKey: ["skills", selectedCat, search],
    queryFn: () => skillsApi.list({
      category: selectedCat === "All" ? undefined : selectedCat,
      search: search || undefined,
    }),
    staleTime: 60_000,
  });

  const { data: agents = [] } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: agentApi.getAgents,
    staleTime: 30_000,
  });

  // Auto-select first agent when agents load and nothing is selected yet
  React.useEffect(() => {
    if (agents.length > 0 && !selectedAgent) {
      setSelectedAgent(agents[0]);
    }
  }, [agents, selectedAgent]);

  const { data: installedSkills = [] } = useQuery<Skill[]>({
    queryKey: ["agent-skills", selectedAgent?.id],
    queryFn: () => skillsApi.getAgentSkills(selectedAgent!.id),
    enabled: !!selectedAgent,
    staleTime: 30_000,
  });

  const [pendingSkillId, setPendingSkillId] = useState<string | null>(null);
  // Optimistic set: IDs, которые мы уже считаем установленными/удалёнными
  // до подтверждения от сервера
  const [optimisticInstalled, setOptimisticInstalled] = useState<Set<string>>(new Set());
  const [optimisticRemoved, setOptimisticRemoved] = useState<Set<string>>(new Set());

  // Итоговый набор: серверные данные + optimistic
  const effectiveInstalledIds = React.useMemo(() => {
    const base = new Set(installedSkills.map((s: Skill) => s.id));
    optimisticInstalled.forEach(id => base.add(id));
    optimisticRemoved.forEach(id => base.delete(id));
    return base;
  }, [installedSkills, optimisticInstalled, optimisticRemoved]);

  const installMutation = useMutation({
    mutationFn: ({ skillId, agentId }: { skillId: string; agentId: string }) =>
      skillsApi.install(agentId, skillId),
    onSuccess: (_data, { skillId, agentId }) => {
      // Сбрасываем optimistic, обновляем реальные данные
      setOptimisticInstalled(prev => { const s = new Set(prev); s.delete(skillId); return s; });
      setPendingSkillId(null);
      qc.invalidateQueries({ queryKey: ["agent-skills", agentId] });
    },
    onError: (_err, { skillId }) => {
      // Откатываем optimistic при ошибке
      setOptimisticInstalled(prev => { const s = new Set(prev); s.delete(skillId); return s; });
      setPendingSkillId(null);
    },
  });

  const uninstallMutation = useMutation({
    mutationFn: ({ skillId, agentId }: { skillId: string; agentId: string }) =>
      skillsApi.uninstall(agentId, skillId),
    onSuccess: (_data, { skillId, agentId }) => {
      setOptimisticRemoved(prev => { const s = new Set(prev); s.delete(skillId); return s; });
      setPendingSkillId(null);
      qc.invalidateQueries({ queryKey: ["agent-skills", agentId] });
    },
    onError: (_err, { skillId }) => {
      setOptimisticRemoved(prev => { const s = new Set(prev); s.delete(skillId); return s; });
      setPendingSkillId(null);
    },
  });

  // Сбрасываем optimistic state при смене агента
  React.useEffect(() => {
    setOptimisticInstalled(new Set());
    setOptimisticRemoved(new Set());
    setPendingSkillId(null);
  }, [selectedAgent?.id]);

  const handleInstall = (skillId: string) => {
    if (!selectedAgent) { setShowAgentPicker(true); return; }
    setPendingSkillId(skillId);
    if (effectiveInstalledIds.has(skillId)) {
      setOptimisticRemoved(prev => new Set([...prev, skillId]));
      uninstallMutation.mutate({ skillId, agentId: selectedAgent.id });
    } else {
      setOptimisticInstalled(prev => new Set([...prev, skillId]));
      installMutation.mutate({ skillId, agentId: selectedAgent.id });
    }
  };

  const initials = (name: string) => name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <h1 className={styles.title}>Skills Market</h1>
          <span className={styles.countBadge}>{skills.length}</span>
        </div>

        {/* Agent picker */}
        <div className={styles.agentSelector} onClick={() => setShowAgentPicker(v => !v)}>
          <div className={styles.selLeft}>
            <div className={styles.selAvatar}>
              {selectedAgent ? initials(selectedAgent.name) : <Package size={16} />}
            </div>
            <div className={styles.selInfo}>
              <span className={styles.selLabel}>Installing for</span>
              <span className={styles.selName}>
                {selectedAgent?.name ?? "Select agent…"}
              </span>
            </div>
          </div>
          <ChevronDown size={16} style={{ transform: showAgentPicker ? "rotate(180deg)" : "none", transition: "0.2s" }} />
        </div>

        {showAgentPicker && (
          <div className={styles.agentDropdown}>
            {agents.length === 0 && (
              <div className={styles.dropdownEmpty}>No agents yet</div>
            )}
            {agents.map((a: Agent) => (
              <button
                key={a.id}
                className={clsx(styles.dropdownItem, selectedAgent?.id === a.id && styles.dropdownItemActive)}
                onClick={() => { setSelectedAgent(a); setShowAgentPicker(false); }}
              >
                <span className={styles.dropdownAvatar}>{initials(a.name)}</span>
                <span>{a.name}</span>
                {selectedAgent?.id === a.id && <Check size={14} style={{ marginLeft: "auto" }} />}
              </button>
            ))}
          </div>
        )}

        <div className={styles.searchBar}>
          <Search size={16} className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Search skills…"
            className={styles.searchInput}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className={styles.categories}>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={clsx(styles.catChip, selectedCat === cat && styles.catChipActive)}
              onClick={() => setSelectedCat(cat)}
            >
              {CAT_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.content}>
        <div className={styles.skillsList}>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => <SkillSkeleton key={i} />)
          ) : skills.length === 0 ? (
            <div className={styles.emptyState}>
              <Zap size={36} className={styles.emptyIcon} />
              <p>No skills found</p>
            </div>
          ) : (
            skills.map((skill) => {
              const isInstalled = effectiveInstalledIds.has(skill.id);
              const isFree = skill.price_ton === "0";
              const isPending = pendingSkillId === skill.id;

              return (
                <div key={skill.id} className={clsx(styles.skillCard, isInstalled && styles.skillCardInstalled)}>
                  <div className={styles.skillHeader}>
                    <div
                      className={styles.skillIcon}
                      style={{ background: `${skill.color}22`, color: skill.color }}
                    >
                      {skill.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className={styles.skillInfo}>
                      <div className={styles.skillNameRow}>
                        <h3 className={styles.skillName}>{skill.name}</h3>
                        <span className={clsx(styles.price, isFree ? styles.priceFree : styles.pricePaid)}>
                          {isFree ? "Free" : `${skill.price_ton} TON`}
                        </span>
                      </div>
                      <span className={styles.skillCat}>{skill.category}</span>
                    </div>
                  </div>

                  <p className={styles.skillDesc}>{skill.description}</p>

                  <div className={styles.skillFooter}>
                    <div className={styles.skillStats}>
                      <div className={styles.stat}>
                        <Star size={12} fill="var(--status-idle)" stroke="var(--status-idle)" />
                        {skill.rating.toFixed(1)}
                      </div>
                      <span className={styles.statValue}>{skill.installs.toLocaleString()} installs</span>
                    </div>

                    {isInstalled ? (
                      <Button
                        variant="outline"
                        className={styles.uninstallBtn}
                        onClick={() => handleInstall(skill.id)}
                        loading={isPending}
                      >
                        <Trash2 size={13} /> Remove
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        className={styles.installBtn}
                        onClick={() => handleInstall(skill.id)}
                        loading={isPending}
                        disabled={!!pendingSkillId && !isPending}
                      >
                        + Install
                      </Button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}

function SkillSkeleton() {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 20, padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 14 }}>
        <Skeleton width={52} height={52} borderRadius="14px" />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          <Skeleton width="60%" height="16px" borderRadius="4px" />
          <Skeleton width="40%" height="12px" borderRadius="4px" />
        </div>
      </div>
      <Skeleton width="100%" height="36px" borderRadius="8px" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Skeleton width="100px" height="18px" borderRadius="20px" />
        <Skeleton width="80px" height="34px" borderRadius="10px" />
      </div>
    </div>
  );
}
