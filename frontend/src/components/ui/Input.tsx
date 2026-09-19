import { useId, type InputHTMLAttributes } from 'react'
import styled from 'styled-components'

export const Input = styled.input<{ $invalid?: boolean }>`
  width: 100%;
  padding: 10px ${({ theme }) => theme.space.md};
  border: 1px solid
    ${({ theme, $invalid }) => ($invalid ? theme.colors.danger : theme.colors.border)};
  border-radius: ${({ theme }) => theme.radii.xs};
  background: ${({ theme }) => theme.colors.background};
  color: ${({ theme }) => theme.colors.heading};
  font-size: ${({ theme }) => theme.fontSizes.md};
  transition: border-color ${({ theme }) => theme.transitions.fast};

  &::placeholder {
    color: ${({ theme }) => theme.colors.muted};
  }
  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.surfaceHover};
  }
  &:focus-visible {
    outline: none;
    border-color: ${({ theme }) => theme.colors.accent};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.accentSoft};
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

const FieldWrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.xs};
  min-width: 0;
`

const Label = styled.label`
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  color: ${({ theme }) => theme.colors.heading};
`

const Message = styled.span<{ $error?: boolean }>`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme, $error }) => ($error ? theme.colors.danger : theme.colors.muted)};
`

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: string
  error?: string
}

/** Input com label, dica e mensagem de erro já ligados por acessibilidade */
export function TextField({ label, hint, error, id, ...rest }: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const messageId = `${inputId}-message`
  const message = error ?? hint

  return (
    <FieldWrapper>
      {label && <Label htmlFor={inputId}>{label}</Label>}
      <Input
        id={inputId}
        $invalid={Boolean(error)}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={message ? messageId : undefined}
        {...rest}
      />
      {message && (
        <Message id={messageId} $error={Boolean(error)}>
          {message}
        </Message>
      )}
    </FieldWrapper>
  )
}
