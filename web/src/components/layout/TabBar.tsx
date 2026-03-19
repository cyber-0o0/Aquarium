"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Zap, Wallet, Settings, Activity } from "lucide-react";
import styles from "./TabBar.module.css";
import { clsx } from "clsx";

const tabs = [
  { id: "agents", label: "Agents", icon: LayoutDashboard, path: "/" },
  { id: "feed", label: "Feed", icon: Activity, path: "/feed" },
  { id: "skills", label: "Skills", icon: Zap, path: "/skills" },
  { id: "wallet", label: "Wallet", icon: Wallet, path: "/wallet" },
  { id: "settings", label: "Settings", icon: Settings, path: "/settings" },
];

export const TabBar = () => {
  const pathname = usePathname();

  return (
    <nav className={styles.tabBar}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
    const isActive = pathname === tab.path || (tab.path !== "/" && pathname.startsWith(tab.path));

    const handleTouch = () => {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
      }
    };

    return (
      <Link
        key={tab.id}
        href={tab.path}
        prefetch={true}
        className={clsx(styles.tabItem, isActive && styles.tabItemActive)}
        onPointerDown={handleTouch}
      >
            <Icon className={styles.icon} />
            <span className={styles.label}>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
};
