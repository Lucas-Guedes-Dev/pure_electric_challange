import styled, { css, keyframes } from 'styled-components'
import { useLiveStatus, type LiveStatus } from '../../graphql/liveStatus'

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 currentColor; }
  70% { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
`

const Wrapper = styled.span<{ $status: LiveStatus }>`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.xs};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  color: ${({ theme, $status }) => ($status === 'connected' ? theme.colors.success : theme.colors.muted)};

  &::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    ${({ $status }) =>
      $status === 'connected' &&
      css`
        animation: ${pulse} 2s infinite;
      `}
  }
`

const LABELS: Record<LiveStatus, string> = {
  idle: 'Tempo real desligado',
  connecting: 'Conectando…',
  connected: 'Ao vivo',
  reconnecting: 'Reconectando…',
}

/** Estado do WebSocket das atualizações em tempo real. */
export function LiveIndicator() {
  const status = useLiveStatus()
  return (
    <Wrapper $status={status} role="status" aria-live="polite">
      {LABELS[status]}
    </Wrapper>
  )
}
