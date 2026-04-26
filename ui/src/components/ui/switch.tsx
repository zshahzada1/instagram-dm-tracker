import * as React from "react"
import { cn } from "../../lib/utils"

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        className={cn(
          "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ig-accent focus-visible:ring-offset-2 focus-visible:ring-offset-ig-background disabled:cursor-not-allowed disabled:opacity-50",
          {
            'bg-ig-border': !checked,
            'bg-ig-accent': checked,
          },
          className
        )}
        onClick={() => onCheckedChange?.(!checked)}
      >
        <span
          className={cn(
            "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform",
            {
              'translate-x-4': checked,
              'translate-x-0': !checked,
            }
          )}
        />
      </button>
    )
  }
)
Switch.displayName = "Switch"

export { Switch }
