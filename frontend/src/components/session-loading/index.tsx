import styled from 'styled-components'
import { Text } from '../ui'

const Wrapper = styled.div`
  display: grid;
  place-items: center;
  min-height: 60vh;
`

/** Exibido enquanto o app pergunta ao backend se há sessão (normalmente uma fração de segundo). */
export function SessionLoading() {
  return (
    <Wrapper role="status" aria-live="polite">
      <Text $tone="muted">Verificando sessão…</Text>
    </Wrapper>
  )
}
