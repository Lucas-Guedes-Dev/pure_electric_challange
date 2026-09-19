import styled from 'styled-components'

export const Dialog = styled.dialog`
  width: min(420px, calc(100vw - 32px));
  padding: ${({ theme }) => theme.space.lg};
  border: 0;
  border-radius: ${({ theme }) => theme.radii.md};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.text};
  box-shadow: ${({ theme }) => theme.shadows.md};

  &::backdrop {
    background: rgb(18 18 18 / 0.6);
  }
`

export const Countdown = styled.strong`
  font-variant-numeric: tabular-nums;
  color: ${({ theme }) => theme.colors.accent};
`

export const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: ${({ theme }) => theme.space.sm};
  margin-top: ${({ theme }) => theme.space.lg};
`
