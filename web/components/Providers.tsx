"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { t, textDirection, type MessageKey } from "@/lib/i18n";
import type { Locale, Me } from "@/lib/types";

type AppState = {
  ready: boolean;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  forgetKey: () => void;
  me: Me | null;
  label: (key: MessageKey) => string;
};

const AppContext = createContext<AppState | null>(null);

function storedLocale(): Locale {
  const value = window.localStorage.getItem("qalam.locale");
  if (value === "ar" || value === "fr" || value === "en") return value;
  return "en";
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [locale, setLocaleState] = useState<Locale>("en");
  const [apiKey, setApiKeyState] = useState("");
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    setLocaleState(storedLocale());
    setApiKeyState(window.localStorage.getItem("qalam.apiKey") || "");
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    document.documentElement.lang = locale;
    document.documentElement.dir = textDirection(locale);
    window.localStorage.setItem("qalam.locale", locale);
  }, [locale, ready]);

  useEffect(() => {
    if (!ready || !apiKey) {
      setMe(null);
      return;
    }
    let cancel = false;
    api<Me>("/v1/me", apiKey)
      .then((profile) => {
        if (!cancel) setMe(profile);
      })
      .catch((error: unknown) => {
        if (cancel) return;
        if (error instanceof ApiError && error.status === 401) {
          window.localStorage.removeItem("qalam.apiKey");
          setApiKeyState("");
        }
        setMe(null);
      });
    return () => {
      cancel = true;
    };
  }, [apiKey, ready]);

  const value = useMemo<AppState>(
    () => ({
      ready,
      locale,
      setLocale: setLocaleState,
      apiKey,
      setApiKey: (key: string) => {
        window.localStorage.setItem("qalam.apiKey", key);
        setApiKeyState(key);
      },
      forgetKey: () => {
        window.localStorage.removeItem("qalam.apiKey");
        setApiKeyState("");
        setMe(null);
      },
      me,
      label: (key) => t(locale, key),
    }),
    [ready, locale, apiKey, me],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside Providers");
  return value;
}
