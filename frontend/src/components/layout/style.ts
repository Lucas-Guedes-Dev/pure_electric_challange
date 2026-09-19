import styled from 'styled-components'
import { media } from '../../styles/theme'

export const LayoutContainer = styled.div`
  display: flex;
  min-height: 100vh;
  background: ${({ theme }) => theme.colors.background};
`

export const Container = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
`

export const Content = styled.main`
  flex: 1;
  padding: ${({ theme }) => `${theme.space.lg} ${theme.space.md} ${theme.space.xxl}`};

  ${media.md} {
    padding: ${({ theme }) => `${theme.space.xl} ${theme.space.xl} ${theme.space.xxl}`};
  }
`
