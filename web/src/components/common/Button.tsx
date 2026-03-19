"use client";

import React from "react";
import styles from "./Button.module.css";
import { clsx } from "clsx";
import { motion } from "framer-motion";

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "style"> {
  variant?: "primary" | "secondary" | "ghost" | "outline" | "destructive";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export const Button = ({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  className,
  disabled,
  ...props
}: ButtonProps) => {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      className={clsx(
        styles.button,
        styles[variant],
        styles[size],
        loading && styles.loading,
        className
      )}
      disabled={loading || disabled}
      {...props}
    >
      {loading ? (
        <span className={styles.spinner} />
      ) : (
        children
      )}
    </motion.button>
  );
};
