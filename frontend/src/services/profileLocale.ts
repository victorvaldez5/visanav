import { isLocale, setLocale, type Locale } from "@/i18n";
import { authService } from "@/services/authService";

/**
 * Keeps the active UI locale and the signed-in user's
 * `Profile.preferred_language` in step. localStorage (via `setLocale`) is the
 * runtime authority; the profile is the durable, cross-device copy.
 */

/** Persist a locale to the signed-in user's profile. Rejects on failure. */
export async function saveProfileLocale(userId: number, locale: Locale): Promise<void> {
  await authService.updateProfile(userId, { preferred_language: locale });
}

/**
 * On sign-in: adopt the profile's language when this browser has no choice of
 * its own yet, otherwise write the browser's choice through to the profile.
 * Best effort: never throws, so it can't block the login flow.
 */
export async function syncLocaleOnLogin(userId: number, hadSavedLocale: boolean, current: Locale): Promise<void> {
  try {
    if (!hadSavedLocale) {
      const profile = await authService.getProfile(userId);
      if (isLocale(profile?.preferred_language)) {
        await setLocale(profile.preferred_language);
        return;
      }
    }
    await saveProfileLocale(userId, current);
  } catch {
    /* the local choice still applies; the profile catches up next change */
  }
}
