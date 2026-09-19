import { Link } from 'react-router-dom'
import styled from 'styled-components'
import { Eyebrow, Heading, Highlight, Stack, Text } from '../components/ui'

const Wrapper = styled.main`
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: ${({ theme }) => theme.space.md};
  text-align: center;
`

const BackLink = styled(Link)`
  align-self: center;
  margin-top: ${({ theme }) => theme.space.md};
  padding: 0.75rem 1.5rem;
  border-radius: ${({ theme }) => theme.radii.pill};
  background: ${({ theme }) => theme.colors.primary};
  color: ${({ theme }) => theme.colors.primaryText};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  text-decoration: none;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.primaryHover};
  }
`

export function NotFoundPage() {
  return (
    <Wrapper>
      <Stack $gap="sm">
        <Eyebrow>Erro 404</Eyebrow>
        <Heading level={1}>
          Página não <Highlight>encontrada.</Highlight>
        </Heading>
        <Text $tone="muted">O endereço acessado não existe ou foi removido.</Text>
        <BackLink to="/inicio">Voltar ao início</BackLink>
      </Stack>
    </Wrapper>
  )
}
