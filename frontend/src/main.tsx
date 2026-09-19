import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import SessionProvider from './components/session-provider'
import { GraphQLProvider } from './graphql/GraphQLProvider'
import App from './routes'
import { AppThemeProvider } from './styles/AppThemeProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppThemeProvider>
      <BrowserRouter>
        <SessionProvider>
          <GraphQLProvider>
            <App />
          </GraphQLProvider>
        </SessionProvider>
      </BrowserRouter>
    </AppThemeProvider>
  </StrictMode>,
)
