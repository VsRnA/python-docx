import type { ButtonHTMLAttributes } from 'react'

import styles from './button.module.css'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>

export function Button({ className, type = 'button', ...props }: ButtonProps) {
  const classes = [styles.button, className].filter(Boolean).join(' ')
  return <button type={type} className={classes} {...props} />
}
