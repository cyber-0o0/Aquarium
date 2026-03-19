"use client";

import React, { useEffect } from 'react';
import { useUIStore } from '@/store/uiStore';

export const ThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const { theme, accentColor } = useUIStore();

  useEffect(() => {
    const applyTheme = () => {
      let activeTheme: 'dark' | 'light' = 'dark';
      
      const twa = (window as any).Telegram?.WebApp;
      if (twa) twa.ready?.();

      if (theme === 'system') {
        if (twa?.colorScheme) {
          activeTheme = twa.colorScheme as 'dark' | 'light';
        } else if (typeof window !== 'undefined') {
          activeTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
      } else {
        activeTheme = theme as 'dark' | 'light';
      }

      // Apply theme attribute
      document.documentElement.setAttribute('data-theme', activeTheme);
      
      const root = document.documentElement;
      
      // If we are in system mode AND have Telegram theme params, use them for a native feel!
      const tp = twa?.themeParams;
      if (theme === 'system' && tp && tp.bg_color) {
        root.style.setProperty('--background', tp.bg_color);
        root.style.setProperty('--foreground', tp.text_color || (activeTheme === 'dark' ? '#FFFFFF' : '#111111'));
        root.style.setProperty('--surface', tp.secondary_bg_color || (activeTheme === 'dark' ? '#141414' : '#FFFFFF'));
        root.style.setProperty('--surface-hover', tp.header_bg_color || (activeTheme === 'dark' ? '#1A1A1A' : '#F9F9F9'));
        
        // Use Telegram's hint_color for borders if it exists
        root.style.setProperty('--border', tp.hint_color ? `color-mix(in srgb, ${tp.hint_color}, transparent 60%)` : (activeTheme === 'dark' ? '#1F1F1F' : '#E5E5E5'));
      } else {
        // Fallback to our own presets
        if (activeTheme === 'dark') {
          root.style.setProperty('--background', '#0A0A0A');
          root.style.setProperty('--foreground', '#FFFFFF');
          root.style.setProperty('--surface', '#141414');
          root.style.setProperty('--surface-hover', '#1A1A1A');
          root.style.setProperty('--border', '#1F1F1F');
        } else {
          root.style.setProperty('--background', '#F5F5F5');
          root.style.setProperty('--foreground', '#111111');
          root.style.setProperty('--surface', '#FFFFFF');
          root.style.setProperty('--surface-hover', '#F9F9F9');
          root.style.setProperty('--border', '#E5E5E5');
        }
      }
      
      // Always apply primary color from our selection (unless user wants native link color too?)
      // Let's stick with our selected accent color but maybe pull it from Telegram too if it's system?
      const finalPrimary = (theme === 'system' && tp?.button_color) ? tp.button_color : accentColor;
      root.style.setProperty('--primary', finalPrimary);
      root.style.setProperty('--primary-foreground', (theme === 'system' && tp?.button_text_color) ? tp.button_text_color : '#000000');
    };

    applyTheme();

    // Listen for system theme changes if set to system
    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handleChange = () => applyTheme();
      mediaQuery.addEventListener('change', handleChange);
      
      // Telegram theme change event
      const twa = (window as any).Telegram?.WebApp;
      if (twa) {
        twa.onEvent?.('themeChanged', handleChange);
      }

      return () => {
        mediaQuery.removeEventListener('change', handleChange);
        if (twa) {
          twa.offEvent?.('themeChanged', handleChange);
        }
      };
    }
  }, [theme, accentColor]);

  return <>{children}</>;
};
