import styled, { css } from 'styled-components'

export type BadgeVariant = 'neutral' | 'accent' | 'success' | 'danger' | 'info'

const variants = {
  neutral: css`
    background: ${({ theme }) => theme.colors.surface};
    color: ${({ theme }) => theme.colors.muted};
  `,
  accent: css`
    background: ${({ theme }) => theme.colors.accentSoft};
    color: ${({ theme }) => theme.colors.heading};
  `,
  success: css`
    background: ${({ theme }) => theme.colors.successSoft};
    color: ${({ theme }) => theme.colors.success};
  `,
  danger: css`
    background: ${({ theme }) => theme.colors.dangerSoft};
    color: ${({ theme }) => theme.colors.danger};
  `,
  info: css`
    background: ${({ theme }) => theme.colors.infoSoft};
    color: ${({ theme }) => theme.colors.info};
  `,
}

export const Badge = styled.span<{ $variant?: BadgeVariant }>`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.xs};
  padding: ${({ theme }) => `${theme.space.xxs} ${theme.space.sm}`};
  border-radius: ${({ theme }) => theme.radii.pill};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  white-space: nowrap;
  ${({ $variant = 'neutral' }) => variants[$variant]}
`
