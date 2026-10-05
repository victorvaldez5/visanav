import { toast } from "vue-sonner";
import { i18n, setLocale, type Locale } from "@/i18n";
import { saveProfileLocale } from "@/services/profileLocale";
import { useAuthStore } from "@/stores/useAuthStore";

/** For the language switcher: switch now, then persist for signed-in users. */
export function useLocaleSync() {
  const auth = useAuthStore();

  async function changeLocale(locale: Locale) {
    try {
      await setLocale(locale);
    } catch {
      toast.error(i18n.global.t("lang.loadError"));
      return;
    }
    if (auth.isAuthenticated && auth.userId !== null) {
      saveProfileLocale(auth.userId, locale).catch(() => {
        toast.error(i18n.global.t("lang.saveError"));
      });
    }
  }

  return { changeLocale };
}
