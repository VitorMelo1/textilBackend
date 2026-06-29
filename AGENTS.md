# AGENTS (Backend)

Diretrizes para agentes de IA neste repositório:

1. Trabalhar apenas no escopo da issue/PR.
2. Não alterar arquivos fora do escopo sem necessidade explícita.
3. Não adicionar dependências sem justificativa técnica clara.
4. Nunca commitar `.env`, tokens, segredos ou credenciais.
5. Criar PRs pequenas, objetivas e incrementais.
6. Sempre explicar como testar a mudança.
7. Rodar checks antes de finalizar:
   - `python -m ruff check .`
   - `python -m ruff format --check .`
   - `python -m pytest` (ou registrar pendência justificada quando não existir)
   - validação de migrations/check equivalente
8. Em caso de dúvida sobre impacto, priorizar segurança e previsibilidade.

