"use client";

import { motion, AnimatePresence } from "framer-motion";
import { usePathname } from "next/navigation";
import { ReactNode, useLayoutEffect } from "react";

export const PageTransition = ({ children }: { children: ReactNode }) => {
  const pathname = usePathname();

  useLayoutEffect(() => {
    // Scroll reset for content-scroll container
    const scrollContainer = document.querySelector('.content-scroll');
    if (scrollContainer) {
      scrollContainer.scrollTo({ top: 0, behavior: 'instant' });
    }
  }, [pathname]);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{
          type: "spring",
          stiffness: 260,
          damping: 30,
        }}
        className="page-wrapper-inner"
        style={{ width: '100%' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
};
