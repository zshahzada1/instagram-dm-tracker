import * as React from "react"
import { cn } from "../../lib/utils"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ig-accent disabled:pointer-events-none disabled:opacity-50",
          {
            'bg-ig-accent text-white hover:bg-blue-600': variant === 'default',
            'bg-red-500 text-white hover:bg-red-600': variant === 'destructive',
            'border border-ig-border bg-transparent hover:bg-ig-surface': variant === 'outline',
            'bg-ig-surface text-ig-text hover:bg-ig-border': variant === 'secondary',
            'hover:bg-ig-surface': variant === 'ghost',
            'text-ig-accent underline-offset-4 hover:underline': variant === 'link',
            'h-9 px-4 py-2': size === 'default',
            'h-8 px-3 text-xs': size === 'sm',
            'h-10 px-8': size === 'lg',
            'h-9 w-9': size === 'icon',
          },
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
