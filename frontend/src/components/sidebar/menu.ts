/**
 * Estrutura da sidebar. Cada seção pode ter título (vira um bloco retrátil) e
 * itens, que são links ou grupos (subseções retráteis, aninháveis à vontade).
 *
 * Ao adicionar um link aqui, registre a rota correspondente em routes/index.tsx.
 */
export interface MenuLink {
  label: string
  to: string
  /** Só marca como ativo na URL exata (ex.: /inicio) */
  end?: boolean
}

export interface MenuGroup {
  label: string
  children: MenuEntry[]
}

export type MenuEntry = MenuLink | MenuGroup

export interface MenuSection {
  id: string
  title?: string
  /** Só aparece para admin (conveniência: quem barra é o AdminRoute e o backend) */
  adminOnly?: boolean
  items: MenuEntry[]
}

export const MENU: MenuSection[] = [
  {
    id: 'geral',
    items: [
      { label: 'Início', to: '/inicio', end: true },
      { label: 'Pedidos', to: '/pedidos' },
    ],
  },
  // Seções só para admin: use `adminOnly: true` (ex.: um futuro cadastro de usuários)
]

export const isMenuLink = (entry: MenuEntry): entry is MenuLink => 'to' in entry
