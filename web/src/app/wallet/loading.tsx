"use client";

import React from "react";
import { Skeleton } from "@/components/common/Skeleton";
import styles from "./page.module.css";

export default function Loading() {
  return (
    <div className={styles.content}>
      <div className={styles.balanceCard}>
         <Skeleton width="100%" height="160px" borderRadius="24px" />
      </div>

      <div className={styles.txList}>
        <TxSkeleton />
        <TxSkeleton />
        <TxSkeleton />
      </div>
    </div>
  );
}

const TxSkeleton = () => (
  <div className={styles.txRow}>
    <div className={styles.txLeft}>
      <Skeleton width={40} height={40} borderRadius="12px" />
      <div className={styles.txInfo}>
        <Skeleton width="80px" height="16px" borderRadius="4px" />
        <div style={{ marginTop: '4px' }}>
          <Skeleton width="60px" height="12px" borderRadius="4px" />
        </div>
      </div>
    </div>
    <div className={styles.txRight} style={{ alignItems: 'flex-end' }}>
      <Skeleton width="50px" height="18px" borderRadius="4px" />
      <div style={{ marginTop: '4px' }}>
        <Skeleton width="30px" height="12px" borderRadius="4px" />
      </div>
    </div>
  </div>
);
