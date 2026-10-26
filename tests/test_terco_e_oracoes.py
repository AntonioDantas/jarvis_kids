from datetime import date, timedelta

from jarvis.dados import carregar_dados
from jarvis.fe.terco import misterios_do_dia


def test_misterios_por_dia_da_semana():
    # 26/10/2026 é segunda-feira
    esperado = ["gozosos", "dolorosos", "gloriosos", "luminosos", "dolorosos", "gozosos", "gloriosos"]
    assert [misterios_do_dia(date(2026, 10, 26) + timedelta(days=i)) for i in range(7)] == esperado


def test_cada_conjunto_tem_cinco_misterios_completos():
    dados = carregar_dados("terco.json")
    assert set(dados["misterios"]) == {"gozosos", "dolorosos", "gloriosos", "luminosos"}
    for conjunto in dados["misterios"].values():
        assert len(conjunto["lista"]) == 5
        for m in conjunto["lista"]:
            assert m["titulo"] and m["referencia"] and m["fruto"] and len(m["meditacao"]) > 40
    for chave in ("oferecimento", "fatima", "salve_rainha"):
        assert dados["oracoes"][chave].strip()


def test_novas_oracoes_tradicionais():
    ids = {o["id"] for o in carregar_dados("oracoes.json")["oracoes"]}
    assert {"angelus", "regina_caeli", "salve_rainha", "vinde_espirito"} <= ids
