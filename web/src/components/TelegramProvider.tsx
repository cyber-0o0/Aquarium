'use client';

import { useEffect, ReactNode, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { authApi, userApi } from '@/services/api';
import { useRouter, usePathname } from 'next/navigation';

export const TelegramProvider = ({ children }: { children: ReactNode }) => {
  const [mounted, setMounted] = useState(false);
  const { setAuth, accessToken, setInitialized } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const bootstrap = async () => {
      if (typeof window === 'undefined') return;

      // Debug console in dev
      if (process.env.NODE_ENV === 'development') {
        import('eruda').then((eruda) => eruda.default.init()).catch(() => {});
      }

      try {

      // ── Step 1: Auth (полностью изолирован от SDK UI-инициализации) ──────
      let authenticated = false;

      // ── Читаем initDataRaw из всех возможных источников ─────────────────
      const getInitDataRaw = (): string => {
        // 1. window.location.hash (стандартный способ в Telegram)
        const hash = window.location.hash.slice(1);
        if (hash && hash.includes('tgWebAppData')) {
          const params = new URLSearchParams(hash);
          const raw = params.get('tgWebAppData');
          if (raw) { console.log('[TG Auth] Source: location.hash'); return raw; }
        }

        // 2. sessionStorage — TonConnect SDK или @tma.js/sdk сохраняют сюда
        // Известные ключи: "ton-connect-session_storage_launchParams", "launchParams", др.
        for (let i = 0; i < sessionStorage.length; i++) {
          const key = sessionStorage.key(i) || '';
          if (key.includes('launchParams') || key.includes('tgWebApp') || key.includes('launch_params')) {
            try {
              const raw = sessionStorage.getItem(key) || '';
              // Формат: JSON { tgWebAppData: "..." } или просто строка
              const parsed = JSON.parse(raw);
              if (parsed?.tgWebAppData) {
                const tgData = parsed.tgWebAppData as string;
                // tgWebAppData должна содержать hash — иначе это только часть данных
                if (tgData.includes('hash') && tgData.includes('auth_date')) {
                  console.log('[TG Auth] Source: sessionStorage key:', key);
                  return tgData;
                }
                // Если hash нет — проверяем другие поля JSON
                // Может быть структура { tgWebAppData, tgWebAppHash, ... }
                const fullData = Object.entries(parsed)
                  .filter(([k]) => k.startsWith('tgWebApp'))
                  .map(([k, v]) => `${k.replace('tgWebApp', '').toLowerCase()}=${v}`)
                  .join('&');
                if (fullData.includes('hash')) {
                  console.log('[TG Auth] Source: sessionStorage reconstructed, key:', key);
                  return fullData;
                }
              }
              // Если само значение — это строка initData
              if (raw.includes('auth_date') && raw.includes('hash')) {
                console.log('[TG Auth] Source: sessionStorage raw, key:', key);
                return raw;
              }
            } catch {
              // не JSON — пробуем как строку
              const raw = sessionStorage.getItem(key) || '';
              if (raw.includes('auth_date') && raw.includes('hash')) {
                console.log('[TG Auth] Source: sessionStorage string, key:', key);
                return raw;
              }
            }
          }
        }

        // 3. @tma.js/sdk retrieveLaunchParams (последний — может падать вне Telegram)
        try {
          // Динамический импорт уже сделан ниже, здесь используем window
          // SDK сам читает из hash/window.__telegram__initParams
          const initParams = (window as any).__telegram__initParams;
          if (initParams?.tgWebAppData) {
            console.log('[TG Auth] Source: window.__telegram__initParams');
            return initParams.tgWebAppData;
          }
        } catch { /* ignore */ }

        return '';
      };

      // Сначала пробуем реальный Telegram initData
      try {
        // Сначала читаем из известных источников
        let initDataRaw = getInitDataRaw();

        // Если не нашли — пробуем через SDK
        if (!initDataRaw) {
          const { retrieveLaunchParams } = await import('@tma.js/sdk');
          const lp = retrieveLaunchParams();
          initDataRaw = (lp.initDataRaw as unknown as string) || '';
        }

        console.log('[TG Auth] initDataRaw:', initDataRaw
          ? initDataRaw.substring(0, 80) + '...'
          : '(empty — not in Telegram)');

        if (initDataRaw) {
          const response = await authApi.loginWithTelegram(initDataRaw);
          useAuthStore.setState({ accessToken: response.access_token });
          const userData = await userApi.getMe();
          setAuth(response.access_token, userData);
          authenticated = true;
          console.log('[TG Auth] ✅ Success:', userData?.username || userData?.telegram_id);
        }
      } catch (e) {
        console.warn('[TG Auth] Real Telegram auth failed:', e);
      }

      /*
      // Dev fallback — всегда выполняется если не авторизовались выше
      if (!authenticated && process.env.NODE_ENV === 'development') {
        // Восстанавливаем существующую сессию
        if (accessToken) {
          try {
            const userData = await userApi.getMe();
            setAuth(accessToken, userData);
            authenticated = true;
            console.log('[TG Auth] Dev session restored');
          } catch {
            console.warn('[TG Auth] Dev session expired, doing fresh login');
          }
        }

        // Свежий dev-логин
        if (!authenticated) {
          try {
            const devData =
              'user=' +
              encodeURIComponent(JSON.stringify({
                id: 12345678,
                first_name: 'Dev',
                last_name: 'User',
                username: 'dev_user',
              })) +
              '&auth_date=' + Math.floor(Date.now() / 1000) +
              '&hash=dev_hash';

            const response = await authApi.loginWithTelegram(devData);
            useAuthStore.setState({ accessToken: response.access_token });
            const userData = await userApi.getMe();
            setAuth(response.access_token, userData);
            authenticated = true;
            console.log('[TG Auth] ✅ Dev auth successful');
          } catch (err) {
            console.error('[TG Auth] Dev auth failed:', err);
          }
        }
      }
      */

      // ── Step 2: Telegram SDK UI (изолирован — не влияет на auth) ─────────
      try {
        const { init, viewport, backButton, themeParams, swipeBehavior, closingBehavior } =
          await import('@tma.js/sdk');

        try { init(); } catch (e) { console.warn('[TG SDK] init() failed (not in Telegram?):', e); }

        viewport.mount()
          .then(() => { 
            viewport.bindCssVars(); 
            if (!viewport.isExpanded()) viewport.expand(); 
            
            // ── Request Fullscreen ──
            const tg = (window as any).Telegram?.WebApp;
            if (tg && typeof tg.requestFullscreen === 'function') {
                try {
                    tg.requestFullscreen();
                    console.log('[TG SDK] Fullscreen requested');
                } catch (e) {
                    console.warn('[TG SDK] Fullscreen request failed:', e);
                }
            } else if (tg) {
                // Fallback to expand if requestFullscreen is not available
                tg.expand();
            }
          })

        if (themeParams.mount.isAvailable()) {
          themeParams.mount();
          themeParams.bindCssVars();
        }
        if (backButton.mount.isAvailable()) backButton.mount();
        if (swipeBehavior.mount.isAvailable()) {
          swipeBehavior.mount();
          swipeBehavior.disableVertical();
        }
        if (closingBehavior.mount.isAvailable()) {
          closingBehavior.mount();
          closingBehavior.enableConfirmation();
        }

        import('@tma.js/sdk').then(({ on }) => {
          on('back_button_pressed', () => router.back());
        });
      } catch (sdkError) {
        console.warn('[TG SDK] UI init failed (ok in browser):', sdkError);
      }

      } catch (fatalError) {
        console.error('[TG] Fatal bootstrap error:', fatalError);
      } finally {
        setInitialized();
        setMounted(true);
      }
    };

    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Back button visibility on route change
  useEffect(() => {
    if (!mounted || typeof window === 'undefined') return;
    import('@tma.js/sdk').then(({ backButton }) => {
      if (!backButton.isMounted()) return;
      if (pathname === '/') backButton.hide();
      else backButton.show();
    }).catch(() => {});
  }, [pathname, mounted]);

  if (!mounted) {
    return (
      <div style={{
        width: '100%', height: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--background)',
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: '50%',
          border: '3px solid var(--border)',
          borderTopColor: 'var(--primary)',
          animation: 'spin 0.7s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return <>{children}</>;
};
