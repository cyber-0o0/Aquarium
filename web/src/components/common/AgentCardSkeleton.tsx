"use client";

import React from "react";
import { Skeleton } from "./Skeleton";
import styles from "./AgentCard.module.css";

export const AgentCardSkeleton = () => {
  return (
    <div className={styles.card} style={{ pointerEvents: 'none' }}>
      <div className={styles.left}>
        <Skeleton width={52} height={52} borderRadius="14px" />
        <div className={styles.info}>
          <div className={styles.nameRow}>
            <Skeleton width="120px" height="18px" borderRadius="4px" />
          </div>
          <div style={{ marginTop: '8px' }}>
            <Skeleton width="100%" height="14px" borderRadius="4px" />
          </div>
          <div className={styles.meta} style={{ marginTop: '12px' }}>
            <Skeleton width="60px" height="20px" borderRadius="100px" />
            <Skeleton width="80px" height="20px" borderRadius="100px" />
          </div>
        </div>
      </div>
    </div>
  );
};
