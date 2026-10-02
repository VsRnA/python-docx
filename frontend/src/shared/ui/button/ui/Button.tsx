import type { ButtonHTMLAttributes } from 'react'

import { cn } from '@/shared/lib/cn'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>

export function Button({ className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'min-h-10 rounded-panel border-0 bg-app-brand px-[18px] font-semibold text-white',
        'cursor-pointer transition-colors hover:bg-app-brandHover',
        'focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 focus-visible:outline-app-brand/30',
        'disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-app-brand',
        className,
      )}
      {...props}
    />
  )
}
