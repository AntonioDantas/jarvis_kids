/* =============================================================================
   J.A.R.V.I.S. Kids — janela futurista
   Recebe eventos do Jarvis (Server-Sent Events) e devolve as respostas da criança.
   Todo texto vindo da IA entra com textContent (nunca como HTML).
   ============================================================================= */
"use strict";

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (id) => document.getElementById(id);
const CORES_LITURGICAS = { verde: "#3ddc84", roxo: "#a46bff", branco: "#f4f7ff", vermelho: "#ff4d5e", rosa: "#ff8fc7" };
const CORES_CATEGORIA = { missa: "#ffd75f", fe: "#d7afff", escola: "#00d7ff", familia: "#ff87d7", esporte: "#5fffaf",
  aniversario: "#ffaf5f", saude: "#ff5f5f", outro: "#87afff" };
const CORES_LETRAS = ["#00e5ff", "#ffd75f", "#b98cff", "#5fffaf", "#ff87d7", "#ffaf5f"];
const LEGENDAS = { ocioso: "ONLINE", atento: "ATENTO", ouvindo: "OUVINDO", pensando: "PENSANDO", falando: "FALANDO" };
const STATUS = { ...LEGENDAS, atento: "DIGA “JARVIS”" };

const app = {
  pedido: null, config: { microfone: false, categorias: {}, repeticoes: {} },
  estado: "ocioso", falando: false, amp: 0, alvoAmp: 0,
  envelope: null, envelopeFps: 30, envelopeInicio: 0, envelopeDuracao: 0,
  calendario: null, categoria: "escola", bootFechado: false, feedMax: 220,
};

/* ------------------------------------------------------------- utilidades */
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined && texto !== null) e.textContent = String(texto);
  return e;
}
function corSegura(cor, padrao = "#00e5ff") {
  return typeof cor === "string" && /^#[0-9a-f]{3,8}$/i.test(cor) ? cor : padrao;
}
async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    ...opcoes,
    headers: { "Content-Type": "application/json", "X-Jarvis-Token": TOKEN, ...(opcoes.headers || {}) },
  });
  let dados = {};
  try { dados = await resposta.json(); } catch (_) { /* sem corpo */ }
  if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);
  return dados;
}

/* ------------------------------------------------------------------ feed */
const feed = $("feed");
function noFim() { return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 140; }
function adicionar(no) {
  const rolar = noFim();
  feed.appendChild(no);
  while (feed.children.length > app.feedMax) feed.firstChild.remove();
  if (rolar) requestAnimationFrame(() => { feed.scrollTop = feed.scrollHeight; });
  return no;
}
function cartao(classe, titulo, cor) {
  const c = el("div", `cartao ${classe}`);
  c.style.setProperty("--cor", corSegura(cor));
  if (titulo) c.appendChild(el("span", "cartao-titulo", titulo));
  return c;
}

function mostrarFala(ev) {
  let c = ev.substitui ? feed.querySelector(`[data-id="${CSS.escape(ev.substitui)}"]`) : null;
  if (!c) {
    c = cartao("fala", `◈ ${ev.titulo || "J.A.R.V.I.S."}`, ev.cor);
    if (ev.substitui) c.dataset.id = ev.substitui;
    c.appendChild(el("span", "fala-texto"));
    adicionar(c);
  }
  const rolar = noFim();
  c.querySelector(".fala-texto").textContent = ev.texto || "";
  if (!ev.ativo && ev.texto) app.ultimaFala = ev.texto;
  c.classList.toggle("ativa", !!ev.ativo);
  if (rolar) feed.scrollTop = feed.scrollHeight;
}
function mostrarCrianca(ev) {
  const c = cartao("crianca", `🗣️ ${ev.nome}`);
  c.appendChild(document.createTextNode(ev.texto));
  adicionar(c);
}
function mostrarLinha(ev) {
  const icones = { aviso: "⚠ ", erro: "✗ ", sucesso: "✓ ", info: "" };
  adicionar(el("div", `linha ${ev.nivel}`, (icones[ev.nivel] || "") + ev.texto));
}
function mostrarPainel(ev) {
  const c = cartao("painel-cartao", ev.titulo, ev.cor);
  c.appendChild(document.createTextNode(ev.texto || ""));
  if (ev.destaque) c.appendChild(el("span", "destaque", `✦ ${ev.destaque}`));
  if (ev.subtitulo) c.appendChild(el("span", "subtitulo", ev.subtitulo));
  adicionar(c);
}
function miniBarra(fracao) {
  const b = el("div", "mini-barra");
  const i = el("i");
  i.style.width = `${Math.round(Math.max(0, Math.min(1, fracao)) * 100)}%`;
  b.appendChild(i);
  return b;
}
function mostrarTabela(ev) {
  const c = cartao("tabela-cartao", ev.titulo, ev.cor);
  const t = el("table");
  const cab = el("tr");
  (ev.colunas || []).forEach((nome) => cab.appendChild(el("th", "", nome)));
  t.appendChild(cab);
  (ev.linhas || []).forEach((linha) => {
    const tr = el("tr");
    linha.forEach((celula) => {
      const td = el("td");
      if (celula && typeof celula === "object" && "barra" in celula) td.appendChild(miniBarra(celula.barra));
      else td.textContent = celula;
      tr.appendChild(td);
    });
    t.appendChild(tr);
  });
  c.appendChild(t);
  adicionar(c);
}
function mostrarQuiz(ev) {
  const c = cartao("quiz-cartao", `🧠 Pergunta ${ev.numero}/${ev.total}`, "#00e5ff");
  c.appendChild(el("div", "pergunta", ev.pergunta));
  const grade = el("div", "quiz-opcoes");
  (ev.opcoes || []).forEach((opcao, i) => {
    const o = el("div", "quiz-opcao");
    const letra = el("span", "letra", "ABCD"[i]);
    letra.style.setProperty("--letra", CORES_LETRAS[i]);
    o.append(letra, document.createTextNode(opcao));
    grade.appendChild(o);
  });
  c.appendChild(grade);
  if (ev.rodape) c.appendChild(el("div", "quiz-rodape", ev.rodape));
  adicionar(c);
}
function mostrarResultado(ev) {
  const r = el("div", `resultado ${ev.correto ? "certo" : "errado"}`, `${ev.correto ? "✔" : "✘"} ${ev.texto}`);
  if (ev.detalhe) r.appendChild(el("small", "", ev.detalhe));
  adicionar(r);
  if (ev.correto) confetes(26);
}
function mostrarOracao(ev) {
  feed.querySelectorAll(".oracao:not(.passada)").forEach((o) => o.classList.add("passada"));
  adicionar(el("div", "oracao", ev.texto));
}
function mostrarContas(ev) {
  feed.querySelectorAll(".contas").forEach((c) => c.remove());
  const c = el("div", "contas");
  c.setAttribute("aria-label", `Conta ${ev.atual} de ${ev.total}`);
  for (let i = 0; i < ev.total; i++) c.appendChild(el("span", `conta${i < ev.atual ? " acesa" : ""}`));
  c.appendChild(el("span", "contas-total", `${ev.atual}/${ev.total}`));
  adicionar(c);
}
function itemAgenda(i, comQuando) {
  const li = el("li", "agenda-item");
  li.style.setProperty("--cat", CORES_CATEGORIA[i.categoria] || "#00e5ff");
  li.appendChild(el("span", "agenda-hora", i.hora || "—"));
  const texto = el("span", "", `${i.emoji} ${i.titulo}`);
  if (comQuando && i.quando) texto.prepend(el("span", "agenda-quando", i.quando));
  li.appendChild(texto);
  return li;
}
function mostrarAgenda(ev) {
  const c = cartao("agenda-cartao", ev.titulo, "#ffd75f");
  const ul = el("ul", "agenda-lista");
  if (!ev.itens.length) ul.appendChild(el("li", "vazio", "Nada marcado."));
  ev.itens.forEach((i) => ul.appendChild(itemAgenda(i)));
  c.appendChild(ul);
  adicionar(c);
}
function mostrarConquista(ev) {
  const grande = ["nivel", "medalha", "missoes"].includes(ev.categoria);
  adicionar(el("div", `chip${grande ? " grande" : ""}`, `✦ ${ev.texto}`));
  if (grande) celebrar(ev);
}

/* ------------------------------------------------------------ celebração */
let tempoCelebracao = null;
function celebrar(ev) {
  const emojis = { nivel: "🚀", medalha: "🏅", missoes: "🌟" };
  const titulos = { nivel: "SUBIU DE NÍVEL!", medalha: "NOVA MEDALHA!", missoes: "DIA PERFEITO!" };
  $("celebracao-emoji").textContent = (ev.texto.match(/\p{Extended_Pictographic}/u) || [emojis[ev.categoria]])[0];
  $("celebracao-titulo").textContent = titulos[ev.categoria];
  $("celebracao-texto").textContent = ev.texto + (ev.detalhe ? ` — ${ev.detalhe}` : "");
  $("celebracao").hidden = false;
  confetes(90);
  clearTimeout(tempoCelebracao);
  tempoCelebracao = setTimeout(() => { $("celebracao").hidden = true; }, 4200);
}
$("celebracao").addEventListener("click", () => { $("celebracao").hidden = true; });
function confetes(quantidade) {
  const caixa = $("confetes");
  const cores = ["#00e5ff", "#ffd75f", "#b98cff", "#5fffaf", "#ff87d7", "#ffaf5f"];
  for (let i = 0; i < quantidade; i++) {
    const c = el("span", "confete");
    c.style.left = `${Math.random() * 100}vw`;
    c.style.background = cores[i % cores.length];
    c.style.animationDuration = `${1.8 + Math.random() * 2.2}s`;
    c.style.animationDelay = `${Math.random() * 0.6}s`;
    c.style.transform = `rotate(${Math.random() * 360}deg)`;
    (caixa.closest("[hidden]") ? document.body : caixa).appendChild(c);
    setTimeout(() => c.remove(), 5200);
  }
}

/* ---------------------------------------------------------- painéis fixos */
function atualizarHud(h) {
  $("hud-nome").textContent = h.nome;
  $("hud-nivel").textContent = h.nivel;
  $("hud-emoji").textContent = h.emoji;
  $("hud-dias").textContent = h.dias;
  $("hud-saldo").textContent = h.saldo;
  const fracao = h.proximo ? (h.pontos - h.minimo) / Math.max(1, h.proximo - h.minimo) : 1;
  $("avatar-xp").style.strokeDashoffset = String(276.5 * (1 - Math.max(0, Math.min(1, fracao))));
  $("hud-xp-texto").textContent = h.proximo ? `${h.pontos} / ${h.proximo} pontos de sabedoria` : `${h.pontos} pontos · nível máximo!`;
  const persona = $("hud-persona");
  persona.hidden = !h.persona;
  persona.textContent = h.persona ? `🎭 Holograma: ${h.persona}` : "";
  const lista = $("lista-missoes");
  lista.replaceChildren();
  (h.missoes || []).forEach((m) => {
    const li = el("li", `missao${m.concluida ? " feita" : ""}`);
    li.appendChild(el("span", "missao-check", m.concluida ? "✓" : ""));
    const corpo = el("div");
    corpo.appendChild(el("div", "missao-nome", m.descricao));
    corpo.appendChild(miniBarra(m.meta ? m.progresso / m.meta : 0));
    li.appendChild(corpo);
    lista.appendChild(li);
  });
}
function atualizarLateral(d) {
  $("lit-data").textContent = d.data;
  $("lit-tempo").textContent = d.liturgia.tempo;
  $("lit-bolinha").style.setProperty("--lit", CORES_LITURGICAS[d.liturgia.cor] || "#3ddc84");
  $("lit-bolinha").title = `Cor litúrgica: ${d.liturgia.cor} (${d.liturgia.significado})`;
  $("lit-celebracao").textContent = d.liturgia.celebracao || "";
  $("lit-ano").textContent = `Cor ${d.liturgia.cor} · Ano ${d.liturgia.ano} (Evangelho de ${d.liturgia.evangelista})`;
  const hoje = $("agenda-hoje");
  hoje.replaceChildren();
  if (!d.hoje.length) hoje.appendChild(el("li", "vazio", "Nada marcado para hoje."));
  d.hoje.forEach((i) => hoje.appendChild(itemAgenda(i)));
  const proximos = $("agenda-proximos");
  proximos.replaceChildren();
  if (!d.proximos.length) proximos.appendChild(el("li", "vazio", "Nada marcado. Que tal usar o planner?"));
  d.proximos.forEach((i) => proximos.appendChild(itemAgenda(i, true)));
  const contagem = $("contagem");
  contagem.replaceChildren();
  d.contagem.forEach((c) => {
    const li = el("li");
    li.appendChild(el("span", "", `${{ Natal: "🎄", "Páscoa": "🐣", Pentecostes: "🔥" }[c.nome] || "✨"} ${c.nome}`));
    const n = el("span");
    n.append(el("b", "", c.dias), el("small", "", c.dias === 1 ? " dia" : " dias"));
    li.appendChild(n);
    contagem.appendChild(li);
  });
}
function adicionarSistema(ev) {
  const simbolo = { true: ["✓", "ok-sim"], null: ["⚠", "ok-talvez"], false: ["✗", "ok-nao"] }[String(ev.ok)];
  for (const lista of [$("lista-sistemas"), $("boot-etapas")]) {
    const li = el("li");
    li.append(el("span", simbolo[1], simbolo[0]), el("b", "", ev.nome));
    if (ev.detalhe) li.appendChild(el("span", "sistema-detalhe", ev.detalhe));
    lista.appendChild(li);
  }
}
function fecharBoot() {
  if (app.bootFechado) return;
  app.bootFechado = true;
  $("boot").classList.add("saiu");
}

/* ------------------------------------------------------- estados e núcleo */
function definirEstado(nome) {
  app.estado = nome;
  document.body.dataset.estado = nome;
  app.corNucleo = null;
  atualizarLegenda();
}
function atualizarLegenda() {
  const nome = app.falando && app.estado === "ocioso" ? "falando" : app.estado;
  $("nucleo-legenda").textContent = LEGENDAS[nome] || "ONLINE";
  $("status-texto").textContent = STATUS[nome] || "ONLINE";
}
function voz(ev) {
  if (ev.fase === "inicio") {
    app.falando = true;
    app.envelope = ev.envelope && ev.envelope.length ? ev.envelope : null;
    app.envelopeFps = ev.fps || 30;
    app.envelopeDuracao = (ev.duracao || 0) * 1000;
    app.envelopeInicio = performance.now();
  } else {
    app.falando = false;
    app.envelope = null;
  }
  document.body.classList.toggle("falando", app.falando);
  app.corNucleo = null;
  atualizarLegenda();
}

const onda = $("onda");
const ctxOnda = onda.getContext("2d");
const BARRAS = 72;
const alturas = new Float32Array(BARRAS);
function animar(agora) {
  let alvo = 0;
  if (app.falando) {
    if (app.envelope) {
      const quadro = Math.floor(((agora - app.envelopeInicio) / 1000) * app.envelopeFps);
      alvo = quadro < app.envelope.length ? app.envelope[quadro] : 0;
    } else {
      alvo = 0.35 + 0.3 * Math.abs(Math.sin(agora / 140));
    }
  } else if (app.estado === "ouvindo" || app.estado === "atento") {
    alvo = app.estado === "atento" ? app.alvoAmp * 0.5 : app.alvoAmp;
  } else if (app.estado === "pensando") {
    alvo = 0.18 + 0.1 * Math.sin(agora / 120);
  }
  app.amp += (alvo - app.amp) * 0.28;
  if (Math.abs(app.amp - app.ampMostrada) > 0.004) {  // só mexe no estilo quando muda de verdade
    app.ampMostrada = app.amp;
    nucleo.style.setProperty("--amp", app.amp.toFixed(3));
  }
  desenharOnda(agora);
  requestAnimationFrame(animar);
}
const nucleo = $("nucleo");
app.ampMostrada = 0;
function desenharOnda(agora) {
  const w = onda.width, h = onda.height, cx = w / 2, cy = h / 2;
  if (app.amp < 0.01 && app.ondaParada) return;  // parado: nada para redesenhar
  app.ondaParada = app.amp < 0.01 && alturas.every((a) => a < 0.5);
  ctxOnda.clearRect(0, 0, w, h);
  if (!app.corNucleo) app.corNucleo = getComputedStyle(document.body).getPropertyValue("--cor-nucleo").trim() || "#00e5ff";
  const cor = app.corNucleo;
  const raio = w * 0.36;
  ctxOnda.lineCap = "round";
  for (let i = 0; i < BARRAS; i++) {
    const ruido = 0.55 + 0.45 * Math.sin(i * 1.7 + agora / 90) * Math.cos(i * 0.6 - agora / 210);
    const alvo = app.amp * ruido * w * 0.11;
    alturas[i] += (alvo - alturas[i]) * 0.35;
    const comprimento = 3 + alturas[i];
    const angulo = (i / BARRAS) * Math.PI * 2 - Math.PI / 2;
    const x1 = cx + Math.cos(angulo) * raio, y1 = cy + Math.sin(angulo) * raio;
    const x2 = cx + Math.cos(angulo) * (raio + comprimento), y2 = cy + Math.sin(angulo) * (raio + comprimento);
    ctxOnda.strokeStyle = cor;
    ctxOnda.globalAlpha = 0.35 + Math.min(0.65, alturas[i] / (w * 0.08));
    ctxOnda.lineWidth = 3;
    ctxOnda.beginPath();
    ctxOnda.moveTo(x1, y1);
    ctxOnda.lineTo(x2, y2);
    ctxOnda.stroke();
  }
  ctxOnda.globalAlpha = 1;
}

/* --------------------------------------------------------- fundo de partículas */
const fundo = $("fundo");
const ctxFundo = fundo.getContext("2d");
let particulas = [];
function prepararFundo() {
  fundo.width = innerWidth;
  fundo.height = innerHeight;
  const n = Math.min(45, Math.round((innerWidth * innerHeight) / 32000));
  particulas = Array.from({ length: n }, () => ({
    x: Math.random() * fundo.width, y: Math.random() * fundo.height,
    vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25, r: Math.random() * 1.6 + 0.4,
  }));
}
function desenharFundo() {
  // Enquanto a IA pensa (ou no modo economia), o fundo fica parado: a CPU vai toda para o cérebro.
  if (document.hidden || app.estado === "pensando" || document.body.classList.contains("economia")) {
    setTimeout(desenharFundo, 300);
    return;
  }
  ctxFundo.clearRect(0, 0, fundo.width, fundo.height);
  for (const p of particulas) {
    p.x = (p.x + p.vx + fundo.width) % fundo.width;
    p.y = (p.y + p.vy + fundo.height) % fundo.height;
    ctxFundo.fillStyle = "rgba(0, 229, 255, .55)";
    ctxFundo.beginPath();
    ctxFundo.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctxFundo.fill();
  }
  ctxFundo.lineWidth = 0.6;
  for (let i = 0; i < particulas.length; i++) {
    for (let j = i + 1; j < particulas.length; j++) {
      const a = particulas[i], b = particulas[j];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d < 130) {
        ctxFundo.strokeStyle = `rgba(0, 229, 255, ${0.12 * (1 - d / 130)})`;
        ctxFundo.beginPath();
        ctxFundo.moveTo(a.x, a.y);
        ctxFundo.lineTo(b.x, b.y);
        ctxFundo.stroke();
      }
    }
  }
  setTimeout(() => requestAnimationFrame(desenharFundo), 66);  // ~15 quadros por segundo bastam
}

/* -------------------------------------------------------------- relógio */
function relogio() {
  const agora = new Date();
  $("hora").textContent = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  $("data-curta").textContent = agora.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" });
}

/* --------------------------------------------------------------- pedidos */
const campo = $("campo");
function responder(valor) {
  if (!app.pedido) return;
  const id = app.pedido.id;
  fecharPedido();
  api("api/responder", { method: "POST", body: JSON.stringify({ id, valor: String(valor) }) }).catch(() => {});
}
function fecharPedido() {
  app.pedido = null;
  document.body.dataset.pedido = "";
  feed.querySelectorAll(".quiz-cartao.respondendo").forEach((c) => c.classList.remove("respondendo"));
  $("modal").hidden = true;
  $("respostas").replaceChildren();
  campo.disabled = true;
  $("btn-enviar").disabled = true;
  $("btn-mic").disabled = true;
  campo.placeholder = "O Jarvis está trabalhando…";
  document.querySelectorAll("#doca button").forEach((b) => { b.disabled = true; });
  $("btn-sair").disabled = true;
}
function botaoResposta(texto, valor, classe = "") {
  const b = el("button", `resposta ${classe}`.trim());
  b.type = "button";
  b.textContent = texto;
  b.addEventListener("click", () => responder(valor));
  return b;
}
function abrirPedido(p) {
  fecharBoot();
  app.pedido = p;
  document.body.dataset.pedido = p.controle;
  document.body.classList.toggle("sem-microfone", !p.microfone);
  const respostas = $("respostas");
  respostas.replaceChildren();
  campo.disabled = false;
  $("btn-enviar").disabled = false;
  $("btn-mic").disabled = !p.microfone;
  const principal = p.controle === "principal";
  document.querySelectorAll("#doca button").forEach((b) => { b.disabled = !principal; });
  $("btn-sair").disabled = !principal;
  const maosLivres = p.escuta === "maos_livres";
  document.body.classList.toggle("escutando-sempre", maosLivres);
  if (principal) {
    campo.placeholder = maosLivres ? "É só falar: “Jarvis, …” — ou digite aqui"
      : p.microfone ? "Aperte FALAR (ou Enter) e fale, ou digite sua pergunta…" : "Digite sua pergunta para o Jarvis…";
  } else {
    campo.placeholder = maosLivres ? `🎙️ Pode responder falando · ${p.rotulo}…` : `${p.rotulo}…`;
  }
  switch (p.controle) {
    case "escolha": abrirEscolha(p); break;
    case "quiz":
      feed.querySelectorAll(".quiz-cartao").forEach((c, i, todos) => c.classList.toggle("respondendo", i === todos.length - 1));
      (p.opcoes || []).forEach((opcao, i) => {
        const b = botaoResposta("", "abcd"[i], "quiz");
        const letra = el("span", "letra", "ABCD"[i]);
        letra.style.setProperty("--letra", CORES_LETRAS[i]);
        b.style.setProperty("--letra", CORES_LETRAS[i]);
        b.append(letra, document.createTextNode(opcao));
        respostas.appendChild(b);
      });
      respostas.appendChild(botaoResposta("⏹ Parar o quiz", "0", "discreta"));
      break;
    case "sim_nao":
      respostas.append(botaoResposta("✅ Sim", "sim", "sim"), botaoResposta("❌ Não", "não", "nao"));
      break;
    case "continuar":
      respostas.appendChild(botaoResposta("Continuar ▶", ""));
      break;
    case "valor": case "numero": case "pin":
      abrirTeclado(p); break;
    default:
      if (/pular/i.test(p.rotulo)) respostas.appendChild(botaoResposta("Pular ▶", "pular", "discreta"));
  }
  if ($("modal").hidden && $("planner").hidden) setTimeout(() => campo.focus(), 30);
}
function abrirEscolha(p) {
  const menu = p.menu || { titulo: "Escolha", opcoes: p.opcoes, pergunta: "" };
  if (menu.opcoes.length <= 4 && menu.opcoes.every((o) => o.length <= 48)) return escolhaNaTela(menu);
  const caixa = $("modal").querySelector(".modal-caixa");
  caixa.style.setProperty("--cor", corSegura(menu.cor));
  $("modal-titulo").textContent = menu.titulo;
  $("modal-pergunta").textContent = menu.pergunta || "";
  const corpo = $("modal-corpo");
  corpo.replaceChildren();
  const grade = el("div", "opcoes");
  menu.opcoes.forEach((opcao, i) => {
    const b = el("button", "opcao");
    b.type = "button";
    const n = el("span", "letra", i + 1);
    n.style.setProperty("--letra", CORES_LETRAS[i % CORES_LETRAS.length]);
    b.append(n, document.createTextNode(opcao));
    b.addEventListener("click", () => responder(i + 1));
    grade.appendChild(b);
  });
  corpo.appendChild(grade);
  const voltar = el("button", "botao opcao-voltar", "↩ Voltar");
  voltar.type = "button";
  voltar.addEventListener("click", () => responder("0"));
  const acoes = el("div", "modal-acoes");
  acoes.appendChild(voltar);
  const falar = botaoFalar(p);
  if (falar) acoes.appendChild(falar);
  corpo.appendChild(acoes);
  $("modal").hidden = false;
  setTimeout(() => grade.querySelector("button")?.focus(), 40);
}
function escolhaNaTela(menu) {
  // Poucas opções: botões grandes na própria tela, sem esconder o que o Jarvis acabou de mostrar.
  const respostas = $("respostas");
  respostas.style.setProperty("--cor", corSegura(menu.cor));
  const titulo = el("div", "respostas-titulo", menu.titulo);
  if (menu.pergunta) titulo.appendChild(el("small", "", menu.pergunta));
  respostas.appendChild(titulo);
  menu.opcoes.forEach((opcao, i) => {
    const b = botaoResposta("", i + 1, "quiz");
    const n = el("span", "letra", i + 1);
    n.style.setProperty("--letra", CORES_LETRAS[i]);
    b.style.setProperty("--letra", CORES_LETRAS[i]);
    b.append(n, document.createTextNode(opcao));
    respostas.appendChild(b);
  });
  respostas.appendChild(botaoResposta("↩ Voltar", "0", "discreta"));
}
function botaoFalar(p) {
  // Dentro das janelinhas o botão FALAR da barra fica coberto: este faz o mesmo papel.
  if (!p.microfone || p.escuta === "maos_livres") return null;
  const b = el("button", "botao botao-falar", "🎙️ Responder falando");
  b.type = "button";
  b.addEventListener("click", () => responder(""));
  return b;
}
function abrirTeclado(p) {
  const tipo = p.controle;
  const caixa = $("modal").querySelector(".modal-caixa");
  caixa.style.setProperty("--cor", tipo === "pin" ? "#ff87d7" : tipo === "valor" ? "#5fffaf" : "#00e5ff");
  $("modal-titulo").textContent = tipo === "pin" ? "🔒 PIN DOS PAIS" : tipo === "valor" ? "💰 VALOR" : "🔢 NÚMERO";
  const generico = /^(número|valor|pin)\b/i.test(p.rotulo);
  $("modal-pergunta").textContent = generico && app.ultimaFala ? app.ultimaFala : p.rotulo;
  const corpo = $("modal-corpo");
  corpo.replaceChildren();
  let digitado = "";
  const visor = el("div", "teclado-visor");
  const mostrar = () => {
    if (tipo === "pin") visor.textContent = "●".repeat(digitado.length) || "· · · ·";
    else if (tipo === "valor") visor.textContent = `R$ ${digitado || "0"}`;
    else visor.textContent = digitado || "0";
  };
  const teclas = ["1", "2", "3", "4", "5", "6", "7", "8", "9", tipo === "valor" ? "," : "⌫", "0", "OK"];
  const teclado = el("div", "teclado");
  teclas.forEach((t) => {
    const b = el("button", t === "OK" ? "ok" : "", t);
    b.type = "button";
    b.addEventListener("click", () => tecla(t));
    teclado.appendChild(b);
  });
  function tecla(t) {
    if (t === "OK") return responder(digitado);
    if (t === "⌫") digitado = digitado.slice(0, -1);
    else if (t === ",") { if (!digitado.includes(",")) digitado = (digitado || "0") + ","; }
    else if (digitado.length < (tipo === "pin" ? 8 : 9)) {
      if (tipo === "valor" && digitado.includes(",") && digitado.split(",")[1].length >= 2) return;
      digitado += t;
    }
    mostrar();
  }
  const acoes = el("div", "teclado-acoes");
  const apagar = el("button", "botao", "⌫ Apagar");
  apagar.type = "button";
  apagar.addEventListener("click", () => tecla("⌫"));
  const voltar = el("button", "botao", "↩ Voltar");
  voltar.type = "button";
  voltar.addEventListener("click", () => responder(tipo === "pin" ? "" : "voltar"));
  acoes.append(apagar, voltar);
  const falar = tipo !== "pin" && botaoFalar(p);
  if (falar) acoes.appendChild(falar);
  corpo.append(visor, teclado, acoes);
  if (tipo !== "pin") {
    corpo.appendChild(el("p", "teclado-dica", p.escuta === "maos_livres"
      ? "🎙️ Mãos-livres ligado: é só falar a resposta (ex.: “dez”, “dois e cinquenta”)."
      : "Você também pode responder falando ou digitando."));
  }
  mostrar();
  $("modal").hidden = false;
  app.tecladoAtual = tecla;
}

/* --------------------------------------------------------------- entrada */
$("form-texto").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!app.pedido) return;
  const texto = campo.value.trim();
  campo.value = "";
  if (!texto && !app.pedido.microfone && app.pedido.controle !== "continuar") return;
  responder(texto);
});
$("btn-mic").addEventListener("click", () => { if (app.pedido) responder(""); });
$("btn-maos-livres").addEventListener("click", () => {
  const ligar = !app.config.maos_livres;
  api("api/acao", { method: "POST", body: JSON.stringify({ acao: ligar ? "maos_livres_ligar" : "maos_livres_desligar" }) })
    .catch(() => {});
});
function mostrarMaosLivres(ligado) {
  const b = $("btn-maos-livres");
  b.setAttribute("aria-pressed", String(!!ligado));
  $("maos-livres-estado").textContent = ligado ? "ligado" : "desligado";
}
$("btn-sair").addEventListener("click", () => {
  if (app.pedido && app.pedido.controle === "principal") responder("tchau");
});
$("btn-silenciar").addEventListener("click", () => {
  api("api/acao", { method: "POST", body: JSON.stringify({ acao: "silenciar" }) }).catch(() => {});
});
$("doca").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-comando]");
  if (!b || b.disabled || !app.pedido || app.pedido.controle !== "principal") return;
  if (b.dataset.comando === "agenda" && !$("planner").hidden) return;
  responder(b.dataset.comando);
});
document.addEventListener("keydown", (e) => {
  if (!$("planner").hidden) {
    if (e.key === "Escape") fecharPlanner();
    return;
  }
  if (!app.pedido) return;
  const tipo = app.pedido.controle;
  if (tipo === "escolha" && document.activeElement !== campo) {
    if (/^[0-9]$/.test(e.key)) { e.preventDefault(); responder(e.key); }
    else if (e.key === "Escape") responder("0");
  } else if (["valor", "numero", "pin"].includes(tipo) && app.tecladoAtual && !$("modal").hidden) {
    if (/^[0-9]$/.test(e.key)) { e.preventDefault(); app.tecladoAtual(e.key); }
    else if (e.key === "," || e.key === ".") { e.preventDefault(); if (tipo === "valor") app.tecladoAtual(","); }
    else if (e.key === "Backspace") { e.preventDefault(); app.tecladoAtual("⌫"); }
    else if (e.key === "Enter") { e.preventDefault(); app.tecladoAtual("OK"); }
    else if (e.key === "Escape") responder(tipo === "pin" ? "" : "voltar");
  }
});
campo.addEventListener("keydown", (e) => {
  if (!app.pedido) return;
  if (app.pedido.controle === "quiz" && campo.value === "" && /^[a-dA-D]$/.test(e.key)) {
    e.preventDefault();
    responder(e.key.toLowerCase());
  }
});

/* --------------------------------------------------------------- planner */
let carregandoCalendario = null;
function carregarScript(src) {
  return new Promise((ok, falha) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = ok;
    s.onerror = falha;
    document.head.appendChild(s);
  });
}
function prepararFormulario() {
  const cats = $("novo-categorias");
  if (cats.children.length) return;
  const categorias = app.config.categorias || {};
  Object.entries(categorias).forEach(([chave, info]) => {
    const b = el("button", "", `${info.emoji} ${info.nome}`);
    b.type = "button";
    b.style.setProperty("--cat", CORES_CATEGORIA[chave] || "#87afff");
    b.setAttribute("aria-pressed", String(chave === app.categoria));
    b.addEventListener("click", () => {
      app.categoria = chave;
      cats.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    });
    cats.appendChild(b);
  });
  const repetir = $("novo-repetir");
  Object.entries(app.config.repeticoes || { "": "não repete" }).forEach(([valor, nome]) => {
    const o = el("option", "", nome);
    o.value = valor;
    repetir.appendChild(o);
  });
  const legenda = $("legenda");
  [["missa", "⛪ Missa"], ["fe", "✝️ Fé"], ...Object.entries(categorias).filter(([c]) => c !== "fe")
    .map(([c, i]) => [c, `${i.emoji} ${i.nome}`])].forEach(([c, nome]) => {
    const s = el("span", "", nome);
    s.style.setProperty("--cat", CORES_CATEGORIA[c] || "#87afff");
    legenda.appendChild(s);
  });
}
function hojeIso() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
async function abrirPlanner() {
  prepararFormulario();
  $("planner").hidden = false;
  if (!$("novo-data").value) $("novo-data").value = hojeIso();
  try {
    if (!window.FullCalendar) {
      carregandoCalendario = carregandoCalendario || carregarScript("static/vendor/fullcalendar/index.global.min.js")
        .then(() => carregarScript("static/vendor/fullcalendar/pt-br.global.min.js"));
      await carregandoCalendario;
    }
  } catch (_) {
    $("calendario").textContent = "Não consegui carregar o calendário.";
    return;
  }
  if (!app.calendario) {
    app.calendario = new FullCalendar.Calendar($("calendario"), {
      locale: "pt-br",
      initialView: innerWidth < 820 ? "listWeek" : "dayGridMonth",
      height: "100%",
      firstDay: 0,
      nowIndicator: true,
      dayMaxEvents: 3,
      eventDisplay: "block",
      eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
      headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,listWeek" },
      buttonText: { today: "Hoje", month: "Mês", week: "Semana", list: "Lista" },
      events: (info, sucesso, falha) => {
        const de = info.startStr.slice(0, 10), ate = info.endStr.slice(0, 10);
        api(`api/agenda?start=${de}&end=${ate}`).then(sucesso).catch(falha);
      },
      dateClick: (info) => {
        $("novo-data").value = info.dateStr.slice(0, 10);
        if (info.dateStr.length > 10) $("novo-hora").value = info.dateStr.slice(11, 16);
        $("detalhe").hidden = true;
        $("novo-nome").focus();
      },
      eventClick: (info) => mostrarDetalhe(info.event),
    });
    app.calendario.render();
  } else {
    app.calendario.refetchEvents();
    app.calendario.updateSize();
  }
  setTimeout(() => $("novo-nome").focus(), 60);
}
function fecharPlanner() {
  $("planner").hidden = true;
  if (app.pedido && $("modal").hidden) campo.focus();
}
function mostrarDetalhe(evento) {
  const p = evento.extendedProps || {};
  const d = $("detalhe");
  d.replaceChildren();
  d.appendChild(el("h3", "", p.automatico ? "✝️ Da Igreja" : "📌 Compromisso"));
  d.appendChild(el("p", "", evento.title));
  const quando = new Date(`${p.data}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  d.appendChild(el("p", "", `${quando}${p.hora ? ` · ${p.hora}` : ""}`));
  if (!p.automatico) {
    const apagar = el("button", "botao botao-apagar", "🗑 Apagar este compromisso");
    apagar.type = "button";
    apagar.addEventListener("click", async () => {
      apagar.disabled = true;
      try {
        await api(`api/agenda?id=${encodeURIComponent(p.id)}`, { method: "DELETE" });
        d.hidden = true;
        app.calendario.refetchEvents();
      } catch (erro) {
        apagar.disabled = false;
        apagar.textContent = erro.message;
      }
    });
    d.appendChild(apagar);
  } else {
    d.appendChild(el("p", "", "Itens da Igreja aparecem sozinhos todo ano."));
  }
  d.hidden = false;
}
$("form-novo").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("novo-msg");
  msg.className = "novo-msg";
  msg.textContent = "Salvando…";
  try {
    await api("api/agenda", { method: "POST", body: JSON.stringify({
      titulo: $("novo-nome").value, data: $("novo-data").value, hora: $("novo-hora").value,
      categoria: app.categoria, repetir: $("novo-repetir").value,
    }) });
    msg.className = "novo-msg ok";
    msg.textContent = "✓ Anotado na agenda!";
    $("novo-nome").value = "";
    $("novo-hora").value = "";
    app.calendario?.refetchEvents();
    confetes(20);
  } catch (erro) {
    msg.className = "novo-msg erro";
    msg.textContent = erro.message;
  }
});
$("btn-planner").addEventListener("click", abrirPlanner);
$("planner-fechar").addEventListener("click", fecharPlanner);
$("planner").addEventListener("click", (e) => { if (e.target === $("planner")) fecharPlanner(); });

/* ------------------------------------------------------- eventos do Jarvis */
function limparTudo() {
  feed.replaceChildren();
  $("lista-sistemas").replaceChildren();
  $("boot-etapas").replaceChildren();
}
const tratadores = {
  reinicio: limparTudo,
  limpar: () => feed.replaceChildren(),
  banner: (ev) => { $("boot-versao").textContent = `v${ev.versao} · 100% local · privacidade total · open-source`; },
  config: (ev) => {
    app.config = ev;
    document.body.classList.toggle("sem-microfone", !ev.microfone);
    document.body.classList.toggle("economia", !!ev.economia);
    mostrarMaosLivres(ev.maos_livres);
  },
  etapa: adicionarSistema,
  carregando: (ev) => {
    $("carregando").hidden = !ev.ativo;
    $("carregando-texto").textContent = ev.texto || "";
    if (ev.ativo && !app.bootFechado) {
      const li = el("li", "", ev.texto);
      $("boot-etapas").appendChild(li);
    }
  },
  progresso: (ev) => {
    const ativo = ev.total > 0 && ev.feito < ev.total;
    const largura = `${ev.total ? Math.round((100 * ev.feito) / ev.total) : 0}%`;
    $("progresso").hidden = !ativo;
    $("progresso-texto").textContent = ev.texto;
    $("progresso-barra").style.width = largura;
    // Na primeira vez o download acontece durante a abertura: a barra aparece lá também.
    $("boot-download").hidden = !ativo;
    $("boot-download-texto").textContent = ev.texto;
    $("boot-download-barra").style.width = largura;
  },
  estado: (ev) => definirEstado(ev.nome),
  nivel_mic: (ev) => { app.alvoAmp = Math.min(1, ev.valor); },
  voz,
  hud: atualizarHud,
  lateral: atualizarLateral,
  fala: (ev) => { fecharBoot(); mostrarFala(ev); },
  crianca: mostrarCrianca,
  aviso: (ev) => {
    mostrarLinha(ev);
    if (!app.bootFechado) $("boot-etapas").appendChild(el("li", `boot-aviso ${ev.nivel}`, ev.texto));
  },
  painel: mostrarPainel,
  tabela: mostrarTabela,
  quiz: mostrarQuiz,
  resultado: mostrarResultado,
  oracao: mostrarOracao,
  contas: mostrarContas,
  agenda: mostrarAgenda,
  conquista: mostrarConquista,
  pedido: abrirPedido,
  pedido_fim: (ev) => { if (app.pedido && app.pedido.id === ev.id) fecharPedido(); },
  abrir_planner: abrirPlanner,
  agenda_mudou: () => app.calendario?.refetchEvents(),
  desligado: () => {
    app.desligado = true;
    fecharPedido();
    const c = $("conexao");
    c.replaceChildren();
    const caixa = el("div");
    caixa.append(el("b", "", "Sistemas desligados. Até a próxima, agente! 👋"), el("br"),
      el("small", "", "Que Deus te abençoe. Você já pode fechar esta janela."));
    c.appendChild(caixa);
    c.hidden = false;
  },
};

function conectar() {
  if (!TOKEN) {
    $("boot-etapas").replaceChildren(el("li", "", "Abra o Jarvis pelo atalho ou pelo terminal (iniciar.bat / iniciar.sh)."));
    return;
  }
  const fonte = new EventSource(`api/eventos?t=${encodeURIComponent(TOKEN)}`);
  let falhas = 0;
  fonte.onopen = () => { falhas = 0; $("conexao").hidden = true; };
  fonte.onerror = () => {
    falhas += 1;
    if (app.desligado) fonte.close();
    else if (falhas > 1) $("conexao").hidden = false;
  };
  fonte.onmessage = (m) => {
    let ev;
    try { ev = JSON.parse(m.data); } catch (_) { return; }
    const tratar = tratadores[ev.tipo];
    if (tratar) {
      try { tratar(ev); } catch (erro) { console.error(ev.tipo, erro); }
    }
  };
}

/* ------------------------------------------------------------------ início */
fecharPedido();
prepararFundo();
addEventListener("resize", prepararFundo);
desenharFundo();
requestAnimationFrame(animar);
relogio();
setInterval(relogio, 15000);
conectar();
