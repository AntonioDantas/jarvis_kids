# 🤝 Como contribuir com o J.A.R.V.I.S. Kids

Obrigado por querer ajudar! Este projeto é usado por **crianças**, então qualidade, segurança e fidelidade à fé
católica vêm antes de qualquer novidade.

## 🙏 Revisão de conteúdo (catequistas, padres, educadores, pais)

A forma mais valiosa de contribuir é revisar e ampliar os arquivos em [`dados/`](dados/):

| Arquivo | O que contém |
|---|---|
| `conhecimento/catecismo_kids.json` | resumos infantis do Catecismo, com referências |
| `santos.json` | personas das "Vozes das Escrituras" (fatos e citações) |
| `historias_biblicas.json` | histórias da Bíblia recontadas |
| `oracoes.json` | orações tradicionais e orações do projeto |
| `quiz.json` | perguntas do Quiz Desafio |
| `exame_consciencia.json` | Inspectorum (Exame de Consciência) |
| `calendario_santos.json` | festas do calendário litúrgico |
| `seguranca.json` | frases de risco e respostas fixas do Guardião |

**Checklist de conteúdo:**

- [ ] Está de acordo com o Catecismo e o Magistério? Inclua a **referência** (ex.: `CIC 1213`, `Mt 6,9-13`).
- [ ] É texto **próprio** (resumo com suas palavras), de domínio público ou de uso comum? Não cole trechos longos
      de obras protegidas por direitos autorais (incluindo o texto oficial do Catecismo e traduções da Bíblia).
- [ ] Citações de santos têm **fonte conhecida**? Na dúvida, não inclua (frases falsamente atribuídas são comuns!).
- [ ] A linguagem é adequada para **9 a 12 anos**, positiva e sem gerar medo ou escrúpulo?
- [ ] Fatos históricos (datas, lugares) foram conferidos?

## 💻 Código

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q          # 149 testes, rodam sem GPU, microfone ou Ollama
ruff check .       # estilo e erros comuns
```

Princípios do projeto:

1. **100% local por padrão.** Recursos que usam internet devem ser opcionais e desligados por padrão, com aviso de
   privacidade (como o Edge-TTS).
2. **Tudo degrada com elegância.** Sem GPU, microfone, PortAudio, Kokoro ou Ollama, o Jarvis continua funcionando
   com uma alternativa (CPU, teclado, voz do sistema, módulos sem IA).
3. **Segurança antes da IA.** Situações de risco têm resposta fixa; a saída da IA passa pelo Guardião antes de ser
   mostrada ou falada. Novas funções que mostram texto da IA devem usar `Interacao.responder_em_fluxo`.
4. **Privacidade da criança.** O Exame de Consciência nunca grava respostas. Não adicione telemetria.
5. **Código em português**, simples e com testes para regras novas (mesada, pontos, filtros, comandos).

## 🛡️ Encontrou um problema de segurança infantil?

Se o Jarvis disse algo inadequado ou deixou passar uma situação de risco, abra uma *issue* com a frase usada (sem
dados pessoais da criança). Isso tem prioridade máxima.

## 💬 Convivência

Seja gentil e respeitoso, como os santos que inspiram este projeto. Críticas são bem-vindas quando construtivas.
