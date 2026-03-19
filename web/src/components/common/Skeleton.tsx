"use client";

import React from "react";
import styles from "./Skeleton.module.css";
import { clsx } from "clsx";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

export const Skeleton = ({ width, height, borderRadius, className, style }: SkeletonProps) => {
  return (
    <div 
      className={clsx(styles.skeleton, className)} 
      style={{ 
        width: typeof width === 'number' ? `${width}px` : width, 
        height: typeof height === 'number' ? `${height}px` : height, 
        borderRadius,
        ...style 
      }} 
    />
  );
};
