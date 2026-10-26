# 📚 Material extra da família ou da paróquia

Coloque aqui conteúdos que o Jarvis deve usar como **fontes verificadas** (RAG local):

* **`.md` ou `.txt`** — textos livres. Cada parágrafo (separado por uma linha em branco) vira um trecho.
  Ex.: `catequese_primeira_comunhao.md`, `historia_da_nossa_paroquia.txt`.
* **`.json`** — mesmo formato de `../catecismo_kids.json`:

```json
{
  "fonte": "Catequese da Paróquia São José",
  "trechos": [
    {
      "id": "paroquia-padroeiro",
      "titulo": "Nosso padroeiro",
      "texto": "Texto em linguagem infantil...",
      "referencias": ["CIC 437"],
      "palavras_chave": ["padroeiro", "paroquia"]
    }
  ]
}
```

Dicas:
* Revise o conteúdo com o catequista ou o padre antes de adicionar. 🙏
* Use apenas textos que você tem o direito de usar (escritos por você, de domínio público ou com licença livre).
* Este arquivo (`LEIA-ME.md`) é ignorado pela busca.
