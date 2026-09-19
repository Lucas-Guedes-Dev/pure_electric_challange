import { describe, expect, it } from 'vitest'
import { graphqlWsUrl } from './client'

const page = (href: string) => new URL(href) as unknown as Location

describe('graphqlWsUrl', () => {
  it('usa a mesma origem da página quando a API é relativa (proxy do Vite / nginx)', () => {
    expect(graphqlWsUrl('/api/graphql', page('http://localhost:5173/pedidos'))).toBe('ws://localhost:5173/api/graphql')
  })

  it('usa wss em HTTPS', () => {
    expect(graphqlWsUrl('/api/graphql', page('https://app.exemplo.com/'))).toBe('wss://app.exemplo.com/api/graphql')
  })

  it('aceita API em outra origem', () => {
    expect(graphqlWsUrl('https://api.exemplo.com/api/graphql', page('https://app.exemplo.com/'))).toBe(
      'wss://api.exemplo.com/api/graphql',
    )
  })
})
