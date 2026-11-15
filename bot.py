"""
Bot de Futebol para Telegram
----------------------------
- Modo "agenda":     envia a lista dos jogos importantes do dia.
- Modo "resultados": quando TODOS os jogos do dia terminarem, envia os resultados (uma vez só).

Fonte dos dados: placar público da ESPN (grátis, sem cadastro).
Configuração: variáveis de ambiente TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")

# ---------------------------------------------------------------------------
# CAMPEONATOS — para tirar um, apague a linha. Para adicionar, coloque o código da ESPN.
# A ordem aqui é a ordem em que aparecem na mensagem.
# ---------------------------------------------------------------------------
CAMPEONATOS = [
    # Brasil e América do Sul
    ("conmebol.libertadores", "🏆 Libertadores"),
    ("conmebol.sudamericana", "🏆 Sul-Americana"),
    ("bra.1", "🇧🇷 Brasileirão Série A"),
    ("bra.2", "🇧🇷 Brasileirão Série B"),
    ("bra.copa_do_brazil", "🇧🇷 Copa do Brasil"),
    # Europa
    ("uefa.champions", "⭐ Champions League"),
    ("uefa.europa", "🟠 Europa League"),
    ("eng.1", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"),
    ("esp.1", "🇪🇸 La Liga"),
    ("ita.1", "🇮🇹 Serie A (Itália)"),
    ("ger.1", "🇩🇪 Bundesliga"),
    ("fra.1", "🇫🇷 Ligue 1"),
    # Arábia Saudita
    ("ksa.1", "🇸🇦 Saudi Pro League"),
    # Seleções
    ("fifa.worldq.conmebol", "🌎 Eliminatórias (América do Sul)"),
    ("fifa.friendly", "🤝 Amistosos de Seleções"),
]

URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard?dates={data}"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def baixar_json(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == tentativas - 1:
                print(f"[aviso] falha ao baixar {url}: {e}")
                return None
            time.sleep(2)


def esc(texto):
    """Escapa caracteres especiais do HTML do Telegram."""
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def carregar_estado():
    try:
        with open(ARQUIVO_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def dia_de_referencia(agora=None):
    """Até as 6h da manhã, ainda conta como o 'dia anterior' (jogos que terminam de madrugada)."""
    agora = agora or datetime.now(FUSO)
    if agora.hour < 6:
        agora -= timedelta(days=1)
    return agora.date()


# ---------------------------------------------------------------------------
# Busca dos jogos
# ---------------------------------------------------------------------------
def ler_jogo(ev, liga_nome):
    comp = (ev.get("competitions") or [{}])[0]
    times = comp.get("competitors") or []
    casa = next((t for t in times if t.get("homeAway") == "home"), times[0] if times else {})
    fora = next((t for t in times if t.get("homeAway") == "away"), times[1] if len(times) > 1 else {})

    status = (ev.get("status") or comp.get("status") or {}).get("type", {})
    inicio = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(FUSO)

    tv = []
    for b in comp.get("broadcasts") or []:
        tv += b.get("names") or []
    for b in comp.get("geoBroadcasts") or []:
        nome = (b.get("media") or {}).get("shortName")
        if nome:
            tv.append(nome)

    def nome_time(t):
        tm = t.get("team") or {}
        return tm.get("shortDisplayName") or tm.get("displayName") or "?"

    def gols_penaltis(t):
        return t.get("score"), t.get("shootoutScore")

    gc, pc = gols_penaltis(casa)
    gf, pf = gols_penaltis(fora)

    return {
        "id": ev.get("id"),
        "liga": liga_nome,
        "inicio": inicio,
        "casa": nome_time(casa),
        "fora": nome_time(fora),
        "gols_casa": gc,
        "gols_fora": gf,
        "pen_casa": pc,
        "pen_fora": pf,
        "estado": status.get("state", "pre"),  # pre / in / post
        "nome_status": status.get("name", ""),  # STATUS_FULL_TIME, STATUS_POSTPONED...
        "detalhe": status.get("shortDetail") or status.get("detail") or "",
        "estadio": (comp.get("venue") or {}).get("fullName", ""),
        "rodada": ((comp.get("notes") or [{}])[0] or {}).get("headline", ""),
        "tv": list(dict.fromkeys(tv)),  # remove repetidos
    }


def buscar_jogos(dia):
    """Retorna dict {nome_do_campeonato: [jogos]} só com jogos que começam no 'dia' (horário de Brasília)."""
    # A ESPN usa datas próprias; buscamos o dia e o seguinte e filtramos pelo horário de Brasília.
    datas = [dia.strftime("%Y%m%d"), (dia + timedelta(days=1)).strftime("%Y%m%d")]
    resultado = {}
    for liga, nome in CAMPEONATOS:
        vistos = set()
        jogos = []
        for d in datas:
            dados = baixar_json(URL_ESPN.format(liga=liga, data=d))
            for ev in (dados or {}).get("events", []):
                try:
                    j = ler_jogo(ev, nome)
                except Exception as e:  # noqa: BLE001
                    print(f"[aviso] jogo ignorado ({liga}): {e}")
                    continue
                if j["id"] in vistos or j["inicio"].date() != dia:
                    continue
                vistos.add(j["id"])
                jogos.append(j)
        if jogos:
            resultado[nome] = sorted(jogos, key=lambda x: x["inicio"])
    return resultado


# ---------------------------------------------------------------------------
# Montagem das mensagens
# ---------------------------------------------------------------------------
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def cabecalho_data(dia):
    return f"{DIAS[dia.weekday()]}, {dia.strftime('%d/%m/%Y')}"


def montar_agenda(dia, jogos_por_liga):
    total = sum(len(v) for v in jogos_por_liga.values())
    linhas = [f"⚽ <b>JOGOS DE HOJE</b> — {cabecalho_data(dia)}", f"<i>{total} jogos importantes • horário de Brasília</i>", ""]
    for liga, jogos in jogos_por_liga.items():
        linhas.append(f"<b>{esc(liga)}</b>")
        for j in jogos:
            linhas.append(f"🕒 <b>{j['inicio'].strftime('%H:%M')}</b>  {esc(j['casa'])} x {esc(j['fora'])}")
            extras = []
            if j["estadio"]:
                extras.append(f"🏟 {esc(j['estadio'])}")
            if j["tv"]:
                extras.append(f"📺 {esc(', '.join(j['tv'][:3]))}")
            if j["rodada"]:
                extras.append(f"📌 {esc(j['rodada'])}")
            if j["nome_status"] in ("STATUS_POSTPONED", "STATUS_CANCELED"):
                extras.append("⚠️ ADIADO/CANCELADO")
            if extras:
                linhas.append("      " + " • ".join(extras))
        linhas.append("")
    linhas.append("📊 Os resultados chegam aqui quando todos os jogos terminarem!")
    return "\n".join(linhas)


def placar(j):
    if j["nome_status"] in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED", "STATUS_SUSPENDED"):
        return f"{esc(j['casa'])} x {esc(j['fora'])} — ⚠️ {esc(j['detalhe'] or 'adiado')}"
    if j["estado"] != "post" or j["gols_casa"] is None:
        return f"{esc(j['casa'])} x {esc(j['fora'])} — sem resultado ainda"
    gc, gf = int(j["gols_casa"]), int(j["gols_fora"])
    casa, fora = esc(j["casa"]), esc(j["fora"])
    pen = ""
    if j["pen_casa"] is not None and j["pen_fora"] is not None:
        pc, pf = int(j["pen_casa"]), int(j["pen_fora"])
        pen = f" (pên. {pc} x {pf})"
        if pc > pf:
            casa = f"<b>{casa}</b>"
        elif pf > pc:
            fora = f"<b>{fora}</b>"
    elif gc > gf:
        casa = f"<b>{casa}</b>"
    elif gf > gc:
        fora = f"<b>{fora}</b>"
    return f"{casa} {gc} x {gf} {fora}{pen}"


def montar_resultados(dia, jogos_por_liga):
    linhas = [f"🏁 <b>RESULTADOS</b> — {cabecalho_data(dia)}", ""]
    for liga, jogos in jogos_por_liga.items():
        linhas.append(f"<b>{esc(liga)}</b>")
        for j in jogos:
            linhas.append(f"• {placar(j)}")
        linhas.append("")
    linhas.append("Amanhã tem mais! ⚽")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def dividir(texto, limite=4000):
    """O Telegram aceita até 4096 caracteres por mensagem; quebra em blocos de campeonato."""
    partes, atual = [], ""
    for bloco in texto.split("\n\n"):
        if len(atual) + len(bloco) + 2 > limite and atual:
            partes.append(atual)
            atual = bloco
        else:
            atual = f"{atual}\n\n{bloco}" if atual else bloco
    if atual:
        partes.append(atual)
    return partes


def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("---- (modo teste: TELEGRAM_TOKEN/CHAT_ID não configurados) ----")
        print(texto)
        return
    for parte in dividir(texto):
        dados = urllib.parse.urlencode({
            "chat_id": chat,
            "text": parte,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=dados)
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
            if not resp.get("ok"):
                raise RuntimeError(f"Telegram recusou: {resp}")
        time.sleep(1)


# ---------------------------------------------------------------------------
# Modos
# ---------------------------------------------------------------------------
def modo_agenda(forcar=False):
    dia = datetime.now(FUSO).date()
    estado = carregar_estado()
    chave = dia.isoformat()
    if estado.get("agenda_enviada") == chave and not forcar:
        print("Agenda de hoje já foi enviada.")
        return
    jogos = buscar_jogos(dia)
    if not jogos:
        enviar_telegram(f"⚽ <b>JOGOS DE HOJE</b> — {cabecalho_data(dia)}\n\nHoje não tem jogo dos campeonatos principais. 😴")
        estado["resultados_enviados"] = chave  # nada a enviar depois
    else:
        enviar_telegram(montar_agenda(dia, jogos))
    estado["agenda_enviada"] = chave
    salvar_estado(estado)


def modo_resultados(forcar=False):
    dia = dia_de_referencia()
    estado = carregar_estado()
    chave = dia.isoformat()
    if estado.get("resultados_enviados") == chave and not forcar:
        print("Resultados desse dia já foram enviados.")
        return
    jogos = buscar_jogos(dia)
    todos = [j for lista in jogos.values() for j in lista]
    if not todos:
        print("Nenhum jogo nesse dia.")
        return

    agora = datetime.now(FUSO)
    pendentes = [j for j in todos if j["estado"] != "post"]
    ultimo_inicio = max(j["inicio"] for j in todos)
    # Segurança: se passou 4h do último jogo e algum ficou travado, manda mesmo assim.
    tempo_esgotado = agora > ultimo_inicio + timedelta(hours=4)

    if pendentes and not forcar and not tempo_esgotado:
        print(f"Ainda faltam {len(pendentes)} jogo(s) terminar: " + ", ".join(f"{j['casa']} x {j['fora']}" for j in pendentes))
        return

    enviar_telegram(montar_resultados(dia, jogos))
    estado["resultados_enviados"] = chave
    salvar_estado(estado)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "auto"
    forcar = "--forcar" in sys.argv
    if modo == "agenda":
        modo_agenda(forcar)
    elif modo == "resultados":
        modo_resultados(forcar)
    else:
        # automático: de manhã manda a agenda; no resto do tempo checa os resultados
        hora = datetime.now(FUSO).hour
        if 6 <= hora < 12:
            modo_agenda()
        modo_resultados()
