import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement | string,
        params: {
          sitekey: string;
          callback?: (token: string) => void;
          'error-callback'?: (error: unknown) => void;
          'expired-callback'?: () => void;
          theme?: 'light' | 'dark' | 'auto';
        },
      ) => string;
      reset: (widgetId: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

export interface TurnstileWidgetProps {
  siteKey?: string;
  onSuccess: (token: string) => void;
  onError?: (err: Error) => void;
}

/**
 * Lightweight Cloudflare Turnstile loader widget per D-10.
 * In development or when site key is not configured, automatically bypasses
 * with a mock development token.
 */
export default function TurnstileWidget({
  siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY,
  onSuccess,
  onError,
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    // In local dev without key, automatically provide token
    if (!siteKey || siteKey.trim() === '') {
      onSuccess('mock-dev-turnstile-token');
      return;
    }

    let isMounted = true;

    const renderWidget = () => {
      if (!isMounted || !containerRef.current || !window.turnstile) return;
      try {
        if (widgetIdRef.current) {
          window.turnstile.remove(widgetIdRef.current);
          widgetIdRef.current = null;
        }
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          theme: 'dark',
          callback: (token: string) => {
            if (isMounted) onSuccess(token);
          },
          'error-callback': (err: unknown) => {
            if (isMounted && onError) {
              onError(new Error(`Turnstile verification error: ${err}`));
            }
          },
        });
      } catch (e) {
        console.warn('[TurnstileWidget] Render exception:', e);
      }
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      const existingScript = document.getElementById('cloudflare-turnstile-script');
      if (!existingScript) {
        const script = document.createElement('script');
        script.id = 'cloudflare-turnstile-script';
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.defer = true;
        script.onload = () => {
          renderWidget();
        };
        script.onerror = () => {
          if (isMounted && onError) {
            onError(new Error('Failed to load Cloudflare Turnstile challenge script.'));
          }
        };
        document.head.appendChild(script);
      } else {
        existingScript.addEventListener('load', renderWidget);
      }
    }

    return () => {
      isMounted = false;
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // ignore
        }
      }
    };
  }, [siteKey, onSuccess, onError]);

  if (!siteKey || siteKey.trim() === '') {
    return null;
  }

  return (
    <div className="flex flex-col items-center justify-center p-2">
      <div ref={containerRef} className="my-1" />
    </div>
  );
}
