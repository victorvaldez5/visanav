import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Button } from "./Button.vue"

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold border border-transparent transition-[transform,box-shadow,background-color] duration-150 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:outline-none",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-button-primary-rest hover:-translate-y-0.5 hover:shadow-button-hover focus-visible:-translate-y-0.5 focus-visible:shadow-button-focus active:translate-y-0 active:shadow-button-pressed disabled:shadow-none disabled:translate-y-0",
        destructive:
          "bg-destructive text-white shadow-button-rest hover:-translate-y-0.5 hover:shadow-button-hover focus-visible:-translate-y-0.5 focus-visible:shadow-button-focus active:translate-y-0 active:shadow-button-pressed disabled:shadow-none disabled:translate-y-0",
        outline:
          "bg-raised text-foreground shadow-button-rest hover:-translate-y-0.5 hover:shadow-button-hover focus-visible:-translate-y-0.5 focus-visible:shadow-button-focus active:translate-y-0 active:shadow-button-pressed disabled:shadow-none disabled:translate-y-0",
        secondary:
          "bg-secondary text-secondary-foreground shadow-button-rest hover:-translate-y-0.5 hover:shadow-button-hover focus-visible:-translate-y-0.5 focus-visible:shadow-button-focus active:translate-y-0 active:shadow-button-pressed disabled:shadow-none disabled:translate-y-0",
        ghost:
          "hover:bg-accent/50 hover:text-accent-foreground focus-visible:shadow-glow-focus",
        link: "text-primary underline decoration-2 decoration-[var(--vn-sunflower-400)] underline-offset-4 focus-visible:shadow-glow-focus",
      },
      size: {
        "default": "h-10 px-4 py-2 has-[>svg]:px-3",
        "sm": "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        "lg": "h-11 rounded-md px-6 has-[>svg]:px-4",
        "icon": "size-10",
        "icon-sm": "size-8",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
