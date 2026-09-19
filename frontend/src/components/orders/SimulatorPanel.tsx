import { useState, type FormEvent } from 'react'
import styled, { css } from 'styled-components'
import type { SimulationScenario } from '../../graphql/generated/graphql'
import { useOrderSimulator } from '../../hooks/useOrders'
import { media } from '../../styles/theme'
import { Alert, Button, Card, Heading, Stack, Text, TextField } from '../ui'

const SCENARIOS: { value: SimulationScenario; title: string; expected: string }[] = [
  { value: 'SUCCESS', title: 'Sucesso', expected: 'Processado na 1ª tentativa' },
  { value: 'UNSTABLE', title: 'Instável', expected: '2 falhas temporárias e processado na 3ª tentativa' },
  { value: 'REJECTED', title: 'Recusado', expected: 'O sistema interno recusa: falha sem nova tentativa' },
  { value: 'TIMEOUT', title: 'Sem resposta', expected: 'Timeout nas 3 tentativas (~30 s) e depois falha' },
  { value: 'RANDOM', title: 'Aleatório', expected: 'Mistura dos cenários acima' },
]

const Options = styled.div`
  display: grid;
  gap: ${({ theme }) => theme.space.sm};

  ${media.md} {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
`

const Option = styled.label<{ $selected: boolean }>`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.xxs};
  padding: ${({ theme }) => theme.space.md};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radii.sm};
  background: ${({ theme }) => theme.colors.background};
  cursor: pointer;

  input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  &:focus-within {
    outline: 2px solid ${({ theme }) => theme.colors.accent};
    outline-offset: 2px;
  }

  ${({ $selected, theme }) =>
    $selected &&
    css`
      border-color: ${theme.colors.accent};
      box-shadow: inset 0 0 0 1px ${theme.colors.accent};
    `}
`

const OptionTitle = styled.span`
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  color: ${({ theme }) => theme.colors.heading};
`

const Footer = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: ${({ theme }) => theme.space.md};

  > :first-child {
    width: 140px;
  }
`

interface SimulatorPanelProps {
  /** Chamado após enviar (a lista é recarregada para mostrar os pedidos novos) */
  onSimulated: () => void
}

/**
 * Faz o papel do sistema externo: envia pedidos pelo mesmo fluxo do webhook, em cenários
 * que o sistema interno simulado responde de formas diferentes.
 */
export function SimulatorPanel({ onSimulated }: SimulatorPanelProps) {
  const { simulate, simulation } = useOrderSimulator()
  const [scenario, setScenario] = useState<SimulationScenario>('SUCCESS')
  const [count, setCount] = useState('3')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFeedback(null)
    const result = await simulate({ input: { scenario, count: Number(count) } })
    if (result.error) {
      setFeedback({ tone: 'danger', text: result.error.graphQLErrors[0]?.message ?? 'Não foi possível simular os pedidos.' })
      return
    }
    const sent = result.data?.simulateOrders.length ?? 0
    setFeedback({
      tone: 'success',
      text: `${sent} ${sent === 1 ? 'pedido enviado' : 'pedidos enviados'}. Acompanhe a mudança de status na lista.`,
    })
    onSimulated()
  }

  return (
    <Card $tone="surface">
      <form onSubmit={handleSubmit}>
        <Stack $gap="md">
          <Stack $gap="xxs">
            <Heading level={4}>Simular pedidos</Heading>
            <Text $tone="muted" $size="sm">
              Envia pedidos como o sistema externo faria, pelo mesmo fluxo do webhook. Escolha como o
              sistema interno (simulado) vai responder. Ele também falha ao acaso em parte das chamadas.
            </Text>
          </Stack>

          <Options role="radiogroup" aria-label="Cenário">
            {SCENARIOS.map((option) => (
              <Option key={option.value} $selected={scenario === option.value}>
                <input
                  type="radio"
                  name="scenario"
                  value={option.value}
                  checked={scenario === option.value}
                  onChange={() => setScenario(option.value)}
                />
                <OptionTitle>{option.title}</OptionTitle>
                <Text $tone="muted" $size="sm">
                  {option.expected}
                </Text>
              </Option>
            ))}
          </Options>

          <Footer>
            <TextField
              label="Quantidade"
              type="number"
              min={1}
              max={20}
              required
              value={count}
              onChange={(event) => setCount(event.target.value)}
            />
            <Button type="submit" variant="accent" disabled={simulation.fetching}>
              {simulation.fetching ? 'Enviando…' : 'Enviar pedidos'}
            </Button>
          </Footer>

          {feedback && <Alert tone={feedback.tone}>{feedback.text}</Alert>}
        </Stack>
      </form>
    </Card>
  )
}
