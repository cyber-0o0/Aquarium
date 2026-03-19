"use client";

import React from "react";
import { AgentCardSkeleton } from "@/components/common/AgentCardSkeleton";
import styles from "./page.module.css";

export default function Loading() {
  return (
    <div className={styles.content}>
      <div className={styles.agentList}>
        <AgentCardSkeleton />
        <AgentCardSkeleton />
        <AgentCardSkeleton />
      </div>
    </div>
  );
}
