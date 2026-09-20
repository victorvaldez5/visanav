import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Badge } from "./Badge.vue"

export const badgeVariants = cva(
  "inline-flex items-center justify-center border-0 rounded-none px-4 py-1 text-xs font-bold w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none transition-[color,box-shadow] overflow-hidden [clip-path:polygon(12px_0,calc(100%-12px)_0,100%_50%,calc(100%-12px)_100%,12px_100%,0_50%)]",
  {
    variants: {
      variant: {
        reassure: "bg-reassure text-reassure-foreground",
        info: "bg-accent text-accent-foreground",
        status: "bg-status text-status-foreground",
        destructive: "bg-destructive text-white",
      },
    },
    defaultVariants: {
      variant: "info",
    },
  },
)
export type BadgeVariants = VariantProps<typeof badgeVariants>
