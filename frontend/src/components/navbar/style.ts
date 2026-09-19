import styled from 'styled-components'
import { media } from '../../styles/theme'

export const Bar = styled.header`
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.md};
  min-height: ${({ theme }) => theme.layout.headerHeight};
  padding: 0 ${({ theme }) => theme.space.md};
  background: ${({ theme }) => theme.colors.background};
  border-bottom: 1px solid ${({ theme }) => theme.colors.surface};

  ${media.md} {
    padding: 0 ${({ theme }) => theme.space.xl};
  }
`

export const MenuButton = styled.button`
  display: inline-grid;
  place-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: ${({ theme }) => theme.radii.pill};
  background: transparent;
  color: ${({ theme }) => theme.colors.heading};
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.surface};
  }

  svg {
    width: 22px;
    height: 22px;
  }

  ${media.md} {
    display: none;
  }
`

export const Actions = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.md};
  margin-left: auto;
  min-width: 0;
`

export const UserInfo = styled.div`
  display: none;
  flex-direction: column;
  align-items: flex-end;
  min-width: 0;
  line-height: ${({ theme }) => theme.lineHeights.tight};

  ${media.sm} {
    display: flex;
  }
`

export const UserName = styled.span`
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  color: ${({ theme }) => theme.colors.heading};
`

export const UserRole = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.muted};
`
