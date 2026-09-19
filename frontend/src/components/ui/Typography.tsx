import type { HTMLAttributes } from 'react'
import styled, { css } from 'styled-components'

type HeadingLevel = 1 | 2 | 3 | 4

const headingSizes = {
  1: css`
    font-size: ${({ theme }) => theme.fontSizes.h1};
  `,
  2: css`
    font-size: ${({ theme }) => theme.fontSizes.h2};
  `,
  3: css`
    font-size: ${({ theme }) => theme.fontSizes.h3};
  `,
  4: css`
    font-size: ${({ theme }) => theme.fontSizes.xl};
  `,
}

const StyledHeading = styled.h2<{ $level: HeadingLevel }>`
  font-weight: ${({ theme }) => theme.fontWeights.black};
  line-height: ${({ theme }) => theme.lineHeights.tight};
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.heading};
  ${({ $level }) => headingSizes[$level]}
`

export interface HeadingProps extends HTMLAttributes<HTMLHeadingElement> {
  level?: HeadingLevel
}

/** Título no estilo do site: caixa alta, peso 900. */
export function Heading({ level = 2, ...rest }: HeadingProps) {
  return <StyledHeading as={`h${level}`} $level={level} {...rest} />
}

/** Trecho de título em laranja, como em "SEU DIA MUDA <Highlight>DE LUGAR.</Highlight>" */
export const Highlight = styled.span`
  color: ${({ theme }) => theme.colors.accent};
`

type TextTone = 'default' | 'muted' | 'danger' | 'success'
type TextSize = 'xs' | 'sm' | 'md' | 'lg'

export const Text = styled.p<{ $tone?: TextTone; $size?: TextSize; $weight?: 'regular' | 'medium' | 'bold' }>`
  font-size: ${({ theme, $size = 'md' }) => theme.fontSizes[$size]};
  font-weight: ${({ theme, $weight = 'regular' }) => theme.fontWeights[$weight]};
  color: ${({ theme, $tone = 'default' }) =>
    ({
      default: theme.colors.text,
      muted: theme.colors.muted,
      danger: theme.colors.danger,
      success: theme.colors.success,
    })[$tone]};
`

/** Rótulo pequeno em caixa alta, como "LANÇAMENTO NO BRASIL" */
export const Eyebrow = styled.span`
  display: block;
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.muted};
`
