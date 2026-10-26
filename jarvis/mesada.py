"""
Mesada por Mérito + Cofrinhos independentes (educação financeira e dízimo).

Como funciona:
  * A criança cadastra as SUAS atividades (domésticas e do dia a dia) e
    escolhe quanto cada uma vale.
  * Ao concluir uma atividade, o valor vai para "aprovação dos pais" (se a
    família ativou um PIN) ou direto para os cofrinhos.
  * Todo dinheiro que entra é dividido automaticamente entre os cofrinhos,
    pelos percentuais que a criança definiu: Dízimo, Poupança, Gastar,
    Ajudar o Próximo — e quantos cofrinhos-meta ela quiser criar.

Os valores são guardados em CENTAVOS (números inteiros) para nunca haver
erro de arredondamento.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from jarvis.armazenamento import Perfil, agora
from jarvis.texto import formatar_reais

VALOR_MAXIMO_ATIVIDADE = 100_00     # R$ 100,00 — evita erros de digitação
MAXIMO_COFRINHOS = 7
MAXIMO_EXTRATO = 500

CATEGORIAS = {
    "casa": "🏠 Casa",
    "escola": "📚 Estudos",
    "familia": "👨‍👩‍👧 Família e Próximo",
    "saude": "💪 Saúde e Rotina",
    "outro": "⭐ Outra",
}

SUGESTOES_ATIVIDADES = [
    ("Arrumar a cama", "casa", "🛏️"),
    ("Lavar ou secar a louça", "casa", "🍽️"),
    ("Guardar os brinquedos e materiais", "casa", "🧸"),
    ("Ajudar a pôr e tirar a mesa", "casa", "🍴"),
    ("Cuidar do pet (água, comida, passeio)", "casa", "🐶"),
    ("Regar as plantas", "casa", "🪴"),
    ("Levar o lixo para fora", "casa", "🗑️"),
    ("Fazer a lição de casa sem reclamar", "escola", "✏️"),
    ("Ler um livro por 30 minutos", "escola", "📖"),
    ("Estudar para a prova", "escola", "🧪"),
    ("Ajudar um irmão ou colega", "familia", "🤝"),
    ("Ligar ou visitar os avós", "familia", "👵"),
    ("Ajudar um vizinho ou alguém que precisa", "familia", "🏘️"),
    ("Escovar os dentes sem precisar lembrar", "saude", "🪥"),
    ("Brincar ao ar livre ou praticar esporte", "saude", "⚽"),
    ("Dormir no horário combinado", "saude", "😴"),
]

DICA_PEDAGOGICA = (
    "Dica do Jarvis: responsabilidades da casa podem valer dinheiro. Já rezar e ir à Missa valem "
    "Pontos de Sabedoria — a fé a gente vive por amor, não por pagamento!"
)


class ErroMesada(ValueError):
    """Erro com mensagem amigável para a criança."""


@dataclass
class ResultadoDeposito:
    distribuicao: dict[str, int] = field(default_factory=dict)   # id do cofrinho -> centavos
    metas_atingidas: list[str] = field(default_factory=list)     # nomes dos cofrinhos


def _novo_id() -> str:
    return uuid.uuid4().hex[:8]


def distribuir(valor: int, percentuais: list[tuple[str, int]]) -> dict[str, int]:
    """
    Divide ``valor`` (centavos) pelos percentuais usando o método dos maiores
    restos: a soma das partes é SEMPRE exatamente igual ao valor.
    """
    total_pct = sum(p for _, p in percentuais)
    if total_pct <= 0:
        raise ErroMesada("Os percentuais dos cofrinhos estão zerados.")
    brutos = [(cid, valor * pct / total_pct) for cid, pct in percentuais]
    partes = {cid: int(b) for cid, b in brutos}
    sobra = valor - sum(partes.values())
    for cid, _bruto in sorted(brutos, key=lambda x: (x[1] - int(x[1])), reverse=True)[:sobra]:
        partes[cid] += 1
    return partes


def simular_poupanca(valor_semanal: int, semanas: int, juros_mensal_pct: float = 0.0) -> list[int]:
    """Saldo (centavos) ao fim de cada semana. Juros aplicados a cada 4 semanas."""
    saldo, historico = 0.0, []
    for semana in range(1, semanas + 1):
        saldo += valor_semanal
        if juros_mensal_pct and semana % 4 == 0:
            saldo *= 1 + juros_mensal_pct / 100
        historico.append(round(saldo))
    return historico


class Mesada:
    def __init__(self, perfil: Perfil):
        self.perfil = perfil

    # ------------------------------------------------------------- consultas
    @property
    def dados(self) -> dict:
        return self.perfil.mesada

    @property
    def cofrinhos(self) -> list[dict]:
        return self.dados["cofrinhos"]

    @property
    def atividades(self) -> list[dict]:
        return self.dados["atividades"]

    @property
    def pendentes(self) -> list[dict]:
        return self.dados["pendentes"]

    def cofrinho(self, cofrinho_id: str) -> dict:
        for c in self.cofrinhos:
            if c["id"] == cofrinho_id:
                return c
        raise ErroMesada("Não encontrei esse cofrinho.")

    def saldo_total(self) -> int:
        return sum(c["saldo"] for c in self.cofrinhos)

    def resumo_falado(self) -> str:
        partes = [f"{c['nome']}: {formatar_reais(c['saldo'])}" for c in self.cofrinhos]
        return f"Você tem {formatar_reais(self.saldo_total())} no total. " + "; ".join(partes) + "."

    # ------------------------------------------------------------ atividades
    def adicionar_atividade(self, nome: str, valor: int, categoria: str = "casa", emoji: str = "⭐") -> dict:
        nome = nome.strip()
        if not nome:
            raise ErroMesada("A atividade precisa de um nome.")
        self._validar_valor(valor, permitir_zero=True)
        if valor > VALOR_MAXIMO_ATIVIDADE:
            raise ErroMesada(f"Uau! O máximo por atividade é {formatar_reais(VALOR_MAXIMO_ATIVIDADE)}.")
        atividade = {"id": _novo_id(), "nome": nome[:60], "valor": valor,
                     "categoria": categoria if categoria in CATEGORIAS else "outro", "emoji": emoji}
        self.atividades.append(atividade)
        self.perfil.salvar()
        return atividade

    def atividade(self, atividade_id: str) -> dict:
        for a in self.atividades:
            if a["id"] == atividade_id:
                return a
        raise ErroMesada("Não encontrei essa atividade.")

    def alterar_valor(self, atividade_id: str, valor: int) -> None:
        self._validar_valor(valor, permitir_zero=True)
        if valor > VALOR_MAXIMO_ATIVIDADE:
            raise ErroMesada(f"O máximo por atividade é {formatar_reais(VALOR_MAXIMO_ATIVIDADE)}.")
        self.atividade(atividade_id)["valor"] = valor
        self.perfil.salvar()

    def remover_atividade(self, atividade_id: str) -> None:
        self.dados["atividades"] = [a for a in self.atividades if a["id"] != atividade_id]
        self.perfil.salvar()

    def concluir_atividade(self, atividade_id: str, precisa_aprovacao: bool) -> tuple[str, ResultadoDeposito | None]:
        """Retorna ("pendente", None), ("sem_valor", None) ou ("creditado", resultado)."""
        atividade = self.atividade(atividade_id)
        if atividade["valor"] == 0:
            return "sem_valor", None
        if precisa_aprovacao:
            self.pendentes.append({"id": _novo_id(), "atividade_id": atividade["id"],
                                   "nome": atividade["nome"], "valor": atividade["valor"], "data": agora()})
            self.perfil.salvar()
            return "pendente", None
        return "creditado", self.depositar(atividade["valor"], f"Atividade: {atividade['nome']}")

    def aprovar(self, pendente_id: str, valor: int | None = None) -> ResultadoDeposito:
        """Os pais podem aprovar com o valor proposto ou com outro (negociação!)."""
        pendente = self._tirar_pendente(pendente_id)
        return self.depositar(pendente["valor"] if valor is None else valor,
                              f"Atividade aprovada: {pendente['nome']}")

    def recusar(self, pendente_id: str) -> dict:
        pendente = self._tirar_pendente(pendente_id)
        self.perfil.salvar()
        return pendente

    def _tirar_pendente(self, pendente_id: str) -> dict:
        for i, p in enumerate(self.pendentes):
            if p["id"] == pendente_id:
                return self.pendentes.pop(i)
        raise ErroMesada("Essa atividade não está mais esperando aprovação.")

    # ------------------------------------------------------------- dinheiro
    def depositar(self, valor: int, descricao: str) -> ResultadoDeposito:
        self._validar_valor(valor)
        partes = distribuir(valor, [(c["id"], c["percentual"]) for c in self.cofrinhos])
        resultado = ResultadoDeposito(distribuicao={k: v for k, v in partes.items() if v})
        for c in self.cofrinhos:
            antes = c["saldo"]
            c["saldo"] += partes.get(c["id"], 0)
            if c.get("meta") and antes < c["meta"] <= c["saldo"]:
                resultado.metas_atingidas.append(c["nome"])
        self._extrato("deposito", valor, None, descricao)
        self.perfil.salvar()
        return resultado

    def transferir(self, origem_id: str, destino_id: str, valor: int) -> list[str]:
        self._validar_valor(valor)
        origem, destino = self.cofrinho(origem_id), self.cofrinho(destino_id)
        if origem is destino:
            raise ErroMesada("Escolha dois cofrinhos diferentes.")
        self._exigir_saldo(origem, valor)
        antes = destino["saldo"]
        origem["saldo"] -= valor
        destino["saldo"] += valor
        self._extrato("transferencia", valor, origem_id, f"{origem['nome']} → {destino['nome']}")
        self.perfil.salvar()
        meta = destino.get("meta")
        return [destino["nome"]] if meta and antes < meta <= destino["saldo"] else []

    def retirar(self, cofrinho_id: str, valor: int, motivo: str) -> None:
        """Gastar dinheiro (ex.: comprar um lanche)."""
        self._validar_valor(valor)
        cofrinho = self.cofrinho(cofrinho_id)
        self._exigir_saldo(cofrinho, valor)
        cofrinho["saldo"] -= valor
        self._extrato("retirada", valor, cofrinho_id, motivo.strip() or "Compra")
        self.perfil.salvar()

    def entregar(self, cofrinho_id: str, valor: int | None = None, destino: str = "") -> int:
        """Entregar o dízimo na paróquia ou uma doação: o dinheiro sai com alegria!"""
        cofrinho = self.cofrinho(cofrinho_id)
        valor = cofrinho["saldo"] if valor is None else valor
        self._validar_valor(valor)
        self._exigir_saldo(cofrinho, valor)
        cofrinho["saldo"] -= valor
        tipo = "dizimo_entregue" if cofrinho["tipo"] == "dizimo" else "doacao_entregue"
        self._extrato(tipo, valor, cofrinho_id, destino or cofrinho["nome"])
        self.perfil.salvar()
        return valor

    # ------------------------------------------------------------ cofrinhos
    def definir_percentuais(self, percentuais: dict[str, int]) -> None:
        if set(percentuais) != {c["id"] for c in self.cofrinhos}:
            raise ErroMesada("Informe o percentual de todos os cofrinhos.")
        if any(p < 0 for p in percentuais.values()):
            raise ErroMesada("Percentual não pode ser negativo.")
        if sum(percentuais.values()) != 100:
            raise ErroMesada(f"A soma precisa dar 100%. Agora está em {sum(percentuais.values())}%.")
        for c in self.cofrinhos:
            c["percentual"] = int(percentuais[c["id"]])
        self.perfil.salvar()

    def criar_cofrinho(self, nome: str, emoji: str = "🎯", meta: int = 0) -> dict:
        if len(self.cofrinhos) >= MAXIMO_COFRINHOS:
            raise ErroMesada(f"Você já tem {MAXIMO_COFRINHOS} cofrinhos. Que tal concluir uma meta antes?")
        if not nome.strip():
            raise ErroMesada("Dê um nome para o seu cofrinho.")
        if meta:
            self._validar_valor(meta)
        cofrinho = {"id": _novo_id(), "nome": nome.strip()[:40], "emoji": emoji, "percentual": 0,
                    "saldo": 0, "meta": meta, "tipo": "meta", "fixo": False}
        self.cofrinhos.append(cofrinho)
        self.perfil.salvar()
        return cofrinho

    def remover_cofrinho(self, cofrinho_id: str) -> None:
        """O saldo e o percentual voltam para a Poupança dos Sonhos."""
        cofrinho = self.cofrinho(cofrinho_id)
        if cofrinho.get("fixo"):
            raise ErroMesada("Esse cofrinho é fixo e não pode ser removido.")
        poupanca = self.cofrinho("poupar")
        poupanca["saldo"] += cofrinho["saldo"]
        poupanca["percentual"] += cofrinho["percentual"]
        self.dados["cofrinhos"] = [c for c in self.cofrinhos if c["id"] != cofrinho_id]
        self.perfil.salvar()

    def definir_meta(self, cofrinho_id: str, valor: int) -> None:
        if valor:
            self._validar_valor(valor)
        self.cofrinho(cofrinho_id)["meta"] = valor
        self.perfil.salvar()

    def extrato(self, quantidade: int = 10) -> list[dict]:
        return list(reversed(self.dados["extrato"][-quantidade:]))

    # --------------------------------------------------------------- apoio
    @staticmethod
    def _validar_valor(valor: int, permitir_zero: bool = False) -> None:
        if not isinstance(valor, int) or valor < 0 or (valor == 0 and not permitir_zero):
            raise ErroMesada("Digite um valor maior que zero, como 2,50.")

    @staticmethod
    def _exigir_saldo(cofrinho: dict, valor: int) -> None:
        if valor > cofrinho["saldo"]:
            raise ErroMesada(
                f"O cofrinho {cofrinho['nome']} só tem {formatar_reais(cofrinho['saldo'])}. "
                "Paciência de astronauta: junte mais um pouco!"
            )

    def _extrato(self, tipo: str, valor: int, cofrinho_id: str | None, descricao: str) -> None:
        self.dados["extrato"].append({"data": agora(), "tipo": tipo, "valor": valor,
                                      "cofrinho": cofrinho_id, "descricao": descricao[:80]})
        del self.dados["extrato"][:-MAXIMO_EXTRATO]
