import styled from 'styled-components'
import type { AppTheme } from '../../styles/theme'

type Space = keyof AppTheme['space']

/** Centraliza o conteúdo com largura máxima e respiro lateral */
export const Container = styled.div`
  width: 100%;
  max-width: ${({ theme }) => theme.layout.maxWidth};
  margin: 0 auto;
  padding: 0 ${({ theme }) => theme.space.md};
`

/** Flexbox com espaçamento vindo do tema: <Stack $direction="row" $gap="md"> */
export const Stack = styled.div<{
  $direction?: 'row' | 'column'
  $gap?: Space
  $align?: 'flex-start' | 'center' | 'flex-end' | 'stretch' | 'baseline'
  $justify?: 'flex-start' | 'center' | 'flex-end' | 'space-between'
  $wrap?: boolean
}>`
  display: flex;
  flex-direction: ${({ $direction = 'column' }) => $direction};
  gap: ${({ theme, $gap = 'md' }) => theme.space[$gap]};
  align-items: ${({ $align = 'stretch' }) => $align};
  justify-content: ${({ $justify = 'flex-start' }) => $justify};
  flex-wrap: ${({ $wrap }) => ($wrap ? 'wrap' : 'nowrap')};
`
