import type { CodegenConfig } from '@graphql-codegen/cli'

/**
 * Gera os tipos TypeScript das operações GraphQL a partir do contrato do backend
 * (backend/schema.graphql). Rode `npm run codegen` sempre que o schema ou uma operação mudar.
 * Os arquivos gerados são versionados: o container do frontend não enxerga ../backend.
 */
const config: CodegenConfig = {
  schema: '../backend/schema.graphql',
  documents: ['src/**/*.{ts,tsx}', '!src/graphql/generated/**'],
  ignoreNoDocuments: true,
  generates: {
    'src/graphql/generated/': {
      preset: 'client',
      presetConfig: { fragmentMasking: false },
      config: {
        // Decimal e DateTime trafegam como string (ex.: "150.00", ISO 8601)
        scalars: { DateTime: 'string', Decimal: 'string' },
        // O tsconfig proíbe `enum` do TypeScript (erasableSyntaxOnly): usa uniões de strings
        enumsAsTypes: true,
        useTypeImports: true,
      },
    },
  },
}

export default config
