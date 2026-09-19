import styled, { css } from 'styled-components'

/** Envolve a tabela para permitir rolagem horizontal em telas estreitas */
export const TableWrapper = styled.div`
  width: 100%;
  overflow-x: auto;
`

export const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: ${({ theme }) => theme.fontSizes.sm};
`

const cell = css<{ $align?: 'left' | 'right' | 'center' }>`
  padding: ${({ theme }) => `${theme.space.sm} ${theme.space.md}`};
  text-align: ${({ $align = 'left' }) => $align};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`

export const Th = styled.th<{ $align?: 'left' | 'right' | 'center' }>`
  ${cell}
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.muted};
  white-space: nowrap;
`

export const Td = styled.td<{ $align?: 'left' | 'right' | 'center' }>`
  ${cell}
  color: ${({ theme }) => theme.colors.text};
  font-variant-numeric: ${({ $align }) => ($align === 'right' ? 'tabular-nums' : 'normal')};
`

export const Tr = styled.tr`
  transition: background ${({ theme }) => theme.transitions.fast};

  tbody &:hover {
    background: ${({ theme }) => theme.colors.surfaceHover};
  }
`
