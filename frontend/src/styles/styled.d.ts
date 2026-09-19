import 'styled-components'
import type { AppTheme } from './theme'

// Tipa o `theme` recebido em todos os styled components
declare module 'styled-components' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefaultTheme extends AppTheme {}
}
