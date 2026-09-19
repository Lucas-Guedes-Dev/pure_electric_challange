/**
 * Tema padrão da aplicação, baseado na identidade visual de pureelectric.com.br
 * (tipografia Work Sans, títulos em caixa alta peso 900, botões pílula pretos e laranja como destaque).
 *
 * Use sempre os tokens daqui nos styled components: `${({ theme }) => theme.colors.primary}`.
 */
export const theme = {
  colors: {
    background: '#ffffff',
    surface: '#f3f3f3',
    surfaceHover: '#f5f5f5',
    text: '#363636',
    heading: '#121212',
    muted: '#595959',
    border: '#cacaca',

    primary: '#121212',
    primaryHover: 'rgb(18 18 18 / 0.87)',
    primaryText: '#ffffff',

    accent: '#ff8000',
    accentHover: '#ffa64d',
    accentText: '#121212',
    accentSoft: 'rgb(255 128 0 / 0.12)',

    success: '#1f7a45',
    successSoft: '#e3f3e9',
    danger: '#c62828',
    dangerSoft: '#fdecea',
    info: '#2980b9',
    infoSoft: '#e5f1f9',

    /** Áreas escuras (cabeçalho, rodapé, banners) */
    inverse: {
      background: '#121212',
      surface: '#1e1e1e',
      border: '#2a2a2a',
      text: '#dbdbdb',
      heading: '#ffffff',
      muted: '#b8b8b8',
    },
  },

  fonts: {
    body: "'Work Sans', system-ui, sans-serif",
    heading: "'Work Sans', system-ui, sans-serif",
  },

  fontWeights: {
    light: 300,
    regular: 400,
    medium: 500,
    bold: 700,
    black: 900,
  },

  fontSizes: {
    xs: '0.75rem',
    sm: '0.875rem',
    md: '1rem',
    lg: '1.125rem',
    xl: '1.375rem',
    h3: 'clamp(1.375rem, 1.25rem + 0.5vw, 1.75rem)',
    h2: 'clamp(1.75rem, 1.574rem + 0.751vw, 2.25rem)',
    h1: 'clamp(2.125rem, 1.905rem + 0.939vw, 2.75rem)',
  },

  lineHeights: {
    tight: 1.15,
    body: 1.4,
  },

  letterSpacings: {
    normal: 'normal',
    wide: '0.02em',
    logo: '0.18em',
  },

  space: {
    xxs: '2px',
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  radii: {
    none: '0',
    xs: '0.2rem',
    sm: '0.6rem',
    md: '0.8rem',
    lg: '1rem',
    pill: '100px',
  },

  shadows: {
    sm: '0 1px 2px rgb(0 0 0 / 0.05)',
    md: '0 4px 16px rgb(0 0 0 / 0.08)',
  },

  transitions: {
    fast: '0.24s cubic-bezier(0.32, 0.72, 0, 1)',
  },

  layout: {
    maxWidth: '72rem',
    headerHeight: '60px',
  },

  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
  },
}

export type AppTheme = typeof theme

/** Helper para media queries: `${media.md} { ... }` */
export const media = {
  sm: `@media (min-width: ${theme.breakpoints.sm})`,
  md: `@media (min-width: ${theme.breakpoints.md})`,
  lg: `@media (min-width: ${theme.breakpoints.lg})`,
}
