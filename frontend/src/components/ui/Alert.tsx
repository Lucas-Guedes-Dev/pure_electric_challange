import type { ReactNode } from 'react'
import styled, { css } from 'styled-components'

export type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const tones = {
  info: css`
    border-color: ${({ theme }) => theme.colors.info};
    background: ${({ theme }) => theme.colors.infoSoft};
  `,
  success: css`
    border-color: ${({ theme }) => theme.colors.success};
    background: ${({ theme }) => theme.colors.successSoft};
  `,
  warning: css`
    border-color: ${({ theme }) => theme.colors.accent};
    background: ${({ theme }) => theme.colors.accentSoft};
  `,
  danger: css`
    border-color: ${({ theme }) => theme.colors.danger};
    background: ${({ theme }) => theme.colors.dangerSoft};
  `,
}

const Box = styled.div<{ $tone: AlertTone }>`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space.sm};
  padding: ${({ theme }) => `${theme.space.sm} ${theme.space.md}`};
  border-left: 3px solid;
  border-radius: ${({ theme }) => theme.radii.xs};
  color: ${({ theme }) => theme.colors.heading};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  ${({ $tone }) => tones[$tone]}
`

export interface AlertProps {
  tone?: AlertTone
  children: ReactNode
  /** Botão ou link à direita (ex.: "tentar de novo") */
  action?: ReactNode
}

/** Aviso em linha. `danger` é anunciado imediatamente por leitores de tela. */
export function Alert({ tone = 'info', children, action }: AlertProps) {
  return (
    <Box $tone={tone} role={tone === 'danger' ? 'alert' : 'status'}>
      <span>{children}</span>
      {action}
    </Box>
  )
}
