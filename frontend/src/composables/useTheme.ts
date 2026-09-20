import { useDark, useToggle } from "@vueuse/core";

// App-wide light/dark theme state.
//
// `useDark` toggles the `dark` class on <html> — which is what the design
// tokens key off (`@custom-variant dark (&:is(.dark *))` in style.css) — and
// persists the choice to localStorage, falling back to the OS preference on
// first visit. Declared at module scope so every caller shares one reactive
// source of truth (the sidebar logo, the header toggle, anything else).
export const isDark = useDark();
export const toggleTheme = useToggle(isDark);

export function useTheme() {
  return { isDark, toggleTheme };
}
