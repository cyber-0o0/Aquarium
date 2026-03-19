"use client";

import React from "react";
import { Skeleton } from "@/components/common/Skeleton";
import styles from "./page.module.css";

export default function Loading() {
  return (
    <div className={styles.content}>
      <SkillSkeleton />
      <SkillSkeleton />
      <SkillSkeleton />
    </div>
  );
}

const SkillSkeleton = () => (
    <div className={styles.skillCard}>
      <div className={styles.skillHeader}>
        <Skeleton width={52} height={52} borderRadius="14px" />
        <div className={styles.skillInfo}>
          <div className={styles.skillNameRow}>
            <Skeleton width="100px" height="18px" borderRadius="4px" />
            <Skeleton width="40px" height="18px" borderRadius="4px" />
          </div>
          <div style={{ marginTop: '8px' }}>
            <Skeleton width="80px" height="14px" borderRadius="4px" />
          </div>
        </div>
      </div>
      <div style={{ marginTop: '4px' }}>
        <Skeleton width="100%" height="32px" borderRadius="4px" />
      </div>
      <div className={styles.skillFooter} style={{ marginTop: '8px' }}>
        <Skeleton width="120px" height="20px" borderRadius="100px" />
        <Skeleton width="80px" height="32px" borderRadius="8px" />
      </div>
    </div>
);
