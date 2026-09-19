import type { ButtonHTMLAttributes } from 'react'
import styled, { css } from 'styled-components'

export type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
}

interface StyledButtonProps {
  $variant: ButtonVariant
  $size: ButtonSize
  $fullWidth: boolean
}

const variants = {
  primary: css`
    background: ${({ theme }) => theme.colors.primary};
    border-color: ${({ theme }) => theme.colors.primary};
    color: ${({ theme }) => theme.colors.primaryText};
    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.primaryHover};
    }
  `,
  secondary: css`
    background: transparent;
    border-color: ${({ theme }) => theme.colors.heading};
    color: ${({ theme }) => theme.colors.heading};
    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.surfaceHover};
    }
  `,
  accent: css`
    background: ${({ theme }) => theme.colors.accent};
    border-color: ${({ theme }) => theme.colors.accent};
    color: ${({ theme }) => theme.colors.accentText};
    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.accentHover};
      border-color: ${({ theme }) => theme.colors.accentHover};
    }
  `,
  ghost: css`
    background: transparent;
    border-color: transparent;
    color: ${({ theme }) => theme.colors.heading};
    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.surface};
    }
  `,
  danger: css`
    background: transparent;
    border-color: ${({ theme }) => theme.colors.danger};
    color: ${({ theme }) => theme.colors.danger};
    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.dangerSoft};
    }
  `,
}

const sizes = {
  sm: css`
    padding: ${({ theme }) => `${theme.space.xs} ${theme.space.md}`};
    font-size: ${({ theme }) => theme.fontSizes.sm};
  `,
  md: css`
    padding: 8px 36px;
    font-size: ${({ theme }) => theme.fontSizes.md};
  `,
  lg: css`
    padding: 12px 44px;
    font-size: ${({ theme }) => theme.fontSizes.lg};
  `,
}

const StyledButton = styled.button<StyledButtonProps>`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.space.sm};
  width: ${({ $fullWidth }) => ($fullWidth ? '100%' : 'auto')};
  border: 1px solid transparent;
  border-radius: ${({ theme }) => theme.radii.pill};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  line-height: ${({ theme }) => theme.lineHeights.body};
  white-space: nowrap;
  cursor: pointer;
  transition:
    background ${({ theme }) => theme.transitions.fast},
    border-color ${({ theme }) => theme.transitions.fast},
    opacity ${({ theme }) => theme.transitions.fast};

  ${({ $variant }) => variants[$variant]}
  ${({ $size }) => sizes[$size]}

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
`

export function Button({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <StyledButton type={type} $variant={variant} $size={size} $fullWidth={fullWidth} {...rest} />
  )
}
