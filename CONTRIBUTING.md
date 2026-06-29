# CONTRIBUTING (Backend)

## Fluxo de branches

- `main`: produção / estável
- `develop`: integração da sprint
- `feature/*`: tarefas individuais
- `fix/*`: correções
- `chore/*`: manutenção

Fluxo recomendado:
1. Criar branch (`feature/...`, `fix/...`, `chore/...`) a partir de `develop`.
2. Abrir PR para `develop`.
3. Após estabilização, promover `develop` para `main`.

## Setup local

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Comandos de qualidade (quando disponíveis)

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m alembic upgrade head --sql
```

Se o comando de teste não existir/estiver sem suíte:
- não inventar comando;
- criar apenas se houver estrutura de teste instalada;
- caso contrário, documentar pendência na issue/PR.

## Política de segurança

- Nunca commitar `.env`, `.env.local`, `.env.*` sensível, tokens, chaves privadas.
- Versionar somente exemplos (`.env.example`).

## Branch protection (GitHub)

Configurar manualmente em `main` e `develop`:
- Require a pull request before merging.
- Require status checks to pass before merging.
- Marcar `quality-gate` como **required check**.

## Escopo e revisão

- PRs pequenas e focadas.
- Não alterar arquivos fora do escopo sem necessidade clara.
- Sempre incluir seção “Como testar” no PR.

