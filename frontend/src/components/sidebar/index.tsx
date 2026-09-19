import { useId, useState, type ReactNode } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { useSession } from '../../utils/session'
import { isMenuLink, MENU, type MenuEntry, type MenuGroup, type MenuSection } from './menu'
import {
  Backdrop,
  Brand,
  Chevron,
  Collapse,
  Dot,
  GroupToggle,
  Nav,
  NavItem,
  NavList,
  Section,
  SectionToggle,
  SidebarContainer,
  StyledNavLink,
} from './style'

/** Algum link dentro destes itens (em qualquer nível) corresponde à URL atual? */
function containsPath(entries: MenuEntry[], pathname: string): boolean {
  return entries.some((entry) =>
    isMenuLink(entry)
      ? matchPath({ path: entry.to, end: entry.end ?? false }, pathname) !== null
      : containsPath(entry.children, pathname),
  )
}

/**
 * Estado de abrir/fechar que se abre sozinho quando a rota ativa passa a estar
 * dentro do bloco (ex.: ao entrar por URL direta), sem fechar o que o usuário abriu.
 */
function useDisclosure(active: boolean, defaultOpen: boolean) {
  const [open, setOpen] = useState(defaultOpen || active)
  const [wasActive, setWasActive] = useState(active)

  if (active !== wasActive) {
    setWasActive(active)
    if (active) setOpen(true)
  }

  return [open, () => setOpen((value) => !value)] as const
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <Chevron $open={open} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </Chevron>
  )
}

function Collapsible({ id, open, children }: { id: string; open: boolean; children: ReactNode }) {
  return (
    <Collapse $open={open}>
      {/* inert: fechado, os links internos saem do Tab e do leitor de tela */}
      <div id={id} inert={!open}>
        {children}
      </div>
    </Collapse>
  )
}

function Group({ group, pathname }: { group: MenuGroup; pathname: string }) {
  const contentId = useId()
  const active = containsPath(group.children, pathname)
  const [open, toggle] = useDisclosure(active, false)

  return (
    <>
      <GroupToggle type="button" $active={active} aria-expanded={open} aria-controls={contentId} onClick={toggle}>
        <Dot />
        {group.label}
        <ChevronIcon open={open} />
      </GroupToggle>
      <Collapsible id={contentId} open={open}>
        <Entries entries={group.children} pathname={pathname} nested />
      </Collapsible>
    </>
  )
}

function Entries({ entries, pathname, nested }: { entries: MenuEntry[]; pathname: string; nested?: boolean }) {
  return (
    <NavList $nested={nested}>
      {entries.map((entry) => (
        <NavItem key={entry.label}>
          {isMenuLink(entry) ? (
            <StyledNavLink to={entry.to} end={entry.end}>
              <Dot />
              {entry.label}
            </StyledNavLink>
          ) : (
            <Group group={entry} pathname={pathname} />
          )}
        </NavItem>
      ))}
    </NavList>
  )
}

function SidebarSection({ section, pathname }: { section: MenuSection; pathname: string }) {
  const contentId = useId()
  const [open, toggle] = useDisclosure(containsPath(section.items, pathname), true)

  if (!section.title) {
    return (
      <Section>
        <Entries entries={section.items} pathname={pathname} />
      </Section>
    )
  }

  return (
    <Section>
      <SectionToggle type="button" aria-expanded={open} aria-controls={contentId} onClick={toggle}>
        {section.title}
        <ChevronIcon open={open} />
      </SectionToggle>
      <Collapsible id={contentId} open={open}>
        <Entries entries={section.items} pathname={pathname} />
      </Collapsible>
    </Section>
  )
}

interface SidebarProps {
  /** Só tem efeito no mobile, onde a sidebar vira gaveta */
  open: boolean
  onClose: () => void
}

function Sidebar({ open, onClose }: SidebarProps) {
  const { pathname } = useLocation()
  // esconder o bloco é só conveniência: quem digitar a URL cai no AdminRoute
  const { isAdmin: admin } = useSession()
  const sections = MENU.filter((section) => !section.adminOnly || admin)

  return (
    <>
      <Backdrop $open={open} onClick={onClose} aria-hidden="true" />
      <SidebarContainer id="sidebar" $open={open}>
        <Brand aria-label="Pure Electric">
          <strong>PURE</strong>&nbsp;<span>ELECTRIC</span>
        </Brand>
        <Nav aria-label="Menu principal">
          {sections.map((section) => (
            <SidebarSection key={section.id} section={section} pathname={pathname} />
          ))}
        </Nav>
      </SidebarContainer>
    </>
  )
}

export default Sidebar
