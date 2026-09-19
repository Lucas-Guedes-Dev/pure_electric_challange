import { NavLink } from 'react-router-dom'
import styled, { css } from 'styled-components'
import { media } from '../../styles/theme'

export const SIDEBAR_WIDTH = '260px'

export const SidebarContainer = styled.aside<{ $open: boolean }>`
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  width: ${SIDEBAR_WIDTH};
  max-width: 85vw;
  height: 100vh;
  height: 100dvh;
  background: ${({ theme }) => theme.colors.inverse.background};
  color: ${({ theme }) => theme.colors.inverse.text};
  transform: translateX(${({ $open }) => ($open ? '0' : '-100%')});
  /* fechada no mobile, some também do Tab e do leitor de tela (após a animação) */
  visibility: ${({ $open }) => ($open ? 'visible' : 'hidden')};
  transition:
    transform ${({ theme }) => theme.transitions.fast},
    visibility 0s linear ${({ $open }) => ($open ? '0s' : '0.24s')};

  ${media.md} {
    position: sticky;
    top: 0;
    flex-shrink: 0;
    transform: none;
    visibility: visible;
    transition: none;
  }
`

export const Brand = styled.div`
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-height: ${({ theme }) => theme.layout.headerHeight};
  padding: 0 ${({ theme }) => theme.space.lg};
  border-bottom: 1px solid ${({ theme }) => theme.colors.inverse.border};
  font-size: ${({ theme }) => theme.fontSizes.lg};
  letter-spacing: ${({ theme }) => theme.letterSpacings.logo};
  color: ${({ theme }) => theme.colors.inverse.heading};
  white-space: nowrap;

  strong {
    font-weight: ${({ theme }) => theme.fontWeights.bold};
  }
  span {
    font-weight: ${({ theme }) => theme.fontWeights.light};
  }
`

export const Nav = styled.nav`
  flex: 1;
  overflow-y: auto;
  padding: ${({ theme }) => `${theme.space.md} ${theme.space.sm} ${theme.space.lg}`};
`

export const Section = styled.div`
  & + & {
    margin-top: ${({ theme }) => theme.space.sm};
    padding-top: ${({ theme }) => theme.space.sm};
    border-top: 1px solid ${({ theme }) => theme.colors.inverse.border};
  }
`

export const NavList = styled.ul<{ $nested?: boolean }>`
  list-style: none;
  margin: 0;
  padding: 0;

  ${({ $nested, theme }) =>
    $nested &&
    css`
      margin: ${theme.space.xxs} 0 ${theme.space.xs} ${theme.space.lg};
      padding-left: ${theme.space.xs};
      border-left: 1px solid ${theme.colors.inverse.border};
    `}
`

export const NavItem = styled.li`
  margin: 0 0 ${({ theme }) => theme.space.xxs};
`

export const Dot = styled.span`
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.45;
`

export const Chevron = styled.svg<{ $open: boolean }>`
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-left: auto;
  transform: rotate(${({ $open }) => ($open ? '180deg' : '0deg')});
  transition: transform ${({ theme }) => theme.transitions.fast};
`

const itemBase = css`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.sm};
  width: 100%;
  padding: 0.625rem ${({ theme }) => theme.space.sm};
  border: 0;
  border-radius: ${({ theme }) => theme.radii.sm};
  background: transparent;
  color: ${({ theme }) => theme.colors.inverse.text};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;

  &:hover {
    background: rgb(255 255 255 / 0.06);
    color: ${({ theme }) => theme.colors.inverse.heading};
  }
`

export const StyledNavLink = styled(NavLink)`
  ${itemBase}

  &.active {
    background: ${({ theme }) => theme.colors.accentSoft};
    color: ${({ theme }) => theme.colors.accent};
    font-weight: ${({ theme }) => theme.fontWeights.bold};
  }

  &.active ${Dot} {
    opacity: 1;
  }
`

/** Cabeçalho de uma subseção retrátil */
export const GroupToggle = styled.button<{ $active: boolean }>`
  ${itemBase}

  ${({ $active, theme }) =>
    $active &&
    css`
      color: ${theme.colors.inverse.heading};
    `}
`

/** Título de uma seção retrátil */
export const SectionToggle = styled.button`
  display: flex;
  align-items: center;
  width: 100%;
  padding: ${({ theme }) => `${theme.space.sm} ${theme.space.sm} ${theme.space.xs}`};
  border: 0;
  background: transparent;
  color: ${({ theme }) => theme.colors.inverse.muted};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
  text-transform: uppercase;
  cursor: pointer;

  &:hover {
    color: ${({ theme }) => theme.colors.inverse.heading};
  }
`

/** Anima abrir/fechar sem precisar medir a altura do conteúdo */
export const Collapse = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows ${({ theme }) => theme.transitions.fast};

  > * {
    min-height: 0;
    overflow: hidden;
  }
`

export const Backdrop = styled.div<{ $open: boolean }>`
  position: fixed;
  inset: 0;
  z-index: 20;
  background: rgb(0 0 0 / 0.45);
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  pointer-events: ${({ $open }) => ($open ? 'auto' : 'none')};
  transition: opacity ${({ theme }) => theme.transitions.fast};

  ${media.md} {
    display: none;
  }
`
