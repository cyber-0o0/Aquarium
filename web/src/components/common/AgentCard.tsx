"use client";

import React from "react";
import { Agent } from "@/types/agent";
import styles from "./AgentCard.module.css";
import { clsx } from "clsx";
import { ChevronRight, Bot } from "lucide-react";
import { motion } from "framer-motion";

interface AgentCardProps {
  agent: Agent;
  onPress?: (agent: Agent) => void;
}

export const AgentCard = React.memo(({ agent, onPress }: AgentCardProps) => {
  return (
    <div 
      className={styles.card} 
      onClick={() => onPress?.(agent)}
    >
      <div className={styles.left}>
        <div className={styles.avatar} style={{ border: `1px solid ${agent.avatarColor}44` }}>
          {agent.avatar_url ? (
            <span style={{ fontSize: 24 }}>{agent.avatar_url}</span>
          ) : (
            <Bot size={28} color={agent.avatarColor || 'var(--primary)'} />
          )}
          <div className={clsx(styles.avatarDot, styles[`${agent.status}Dot`])} />
        </div>
        
        <div className={styles.info}>
          <div className={styles.nameRow}>
            <span className={styles.name}>{agent.name}</span>
            <span className={clsx(styles.statusLabel, styles[`status_${agent.status}`])}>
              {agent.status}
            </span>
          </div>
          <p className={styles.desc}>{agent.description}</p>
          <div className={styles.meta}>
            <span className={styles.tag}>{agent.model}</span>
            <span className={styles.tag}>{agent.tasksToday} Tasks</span>
          </div>
        </div>
      </div>
      
      <ChevronRight className={styles.chevron} size={20} />
    </div>
  );
});

