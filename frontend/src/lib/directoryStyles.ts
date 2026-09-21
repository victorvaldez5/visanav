// Tailwind class strings shared by the two resource-directory views
// (Organizations + Representatives), kept in one place so they stay in sync.

// A native <select> styled like the app's Input: flat at rest, glow on focus,
// larger touch target on phones. Compose with extra classes for variants — the
// compact toolbar sort adds `md:h-[34px] md:w-auto md:text-sm`.
export const selectClass =
  "h-[38px] w-full rounded-[4px] border border-transparent bg-field px-3 text-[15px] text-foreground shadow-elevation-1-control outline-none transition-[box-shadow] focus-visible:shadow-glow-focus max-md:h-[46px] max-md:text-base";

// The underlined "jump to the other directory" text link at the foot of a card.
export const crossLinkClass =
  "ml-auto inline-flex cursor-pointer items-center gap-1.5 rounded border-0 bg-transparent p-0 font-sans text-sm font-semibold text-foreground underline decoration-[color:var(--vn-sunflower-400)] decoration-2 underline-offset-4 outline-none hover:decoration-[3px] focus-visible:shadow-glow-focus max-md:ml-0 max-md:w-full max-md:justify-center max-md:pt-1";
