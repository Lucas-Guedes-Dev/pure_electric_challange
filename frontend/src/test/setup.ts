import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Sem as globais do Vitest, a Testing Library não desmonta sozinha entre os testes
afterEach(() => cleanup())
