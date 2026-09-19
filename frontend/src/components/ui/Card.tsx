import styled, { css } from 'styled-components'
import type { AppTheme } from '../../styles/theme'

type CardTone = 'default' | 'surface' | 'inverse'

const tones = {
  default: css`
    background: ${({ theme }) => theme.colors.background};
    border-color: ${({ theme }) => theme.colors.border};
  `,
  surface: css`
    background: ${({ theme }) => theme.colors.surface};
    border-color: transparent;
  `,
  inverse: css`
    background: ${({ theme }) => theme.colors.inverse.background};
    border-color: ${({ theme }) => theme.colors.inverse.border};
    color: ${({ theme }) => theme.colors.inverse.text};

    h1, h2, h3, h4 {
      color: ${({ theme }) => theme.colors.inverse.heading};
    }
    p {
      color: ${({ theme }) => theme.colors.inverse.text};
    }
  `,
}

export const Card = styled.section<{ $tone?: CardTone; $padding?: keyof AppTheme['space'] }>`
  border: 1px solid transparent;
  border-radius: ${({ theme }) => theme.radii.md};
  padding: ${({ theme, $padding = 'lg' }) => theme.space[$padding]};
  ${({ $tone = 'default' }) => tones[$tone]}
`
