import * as React from "react"
import { cn } from "../../lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline'
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-1 focus:ring-ig-accent",
        {
          'border-transparent bg-ig-accent text-white': variant === 'default',
          'border-transparent bg-ig-surface text-ig-text': variant === 'secondary',
          'border-transparent bg-red-500 text-white': variant === 'destructive',
          'text-ig-text': variant === 'outline',
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
