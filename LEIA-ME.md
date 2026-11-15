# ⚽ Bot de Futebol para Telegram — Passo a passo

O bot faz duas coisas, sozinho, todo dia:
1. **De manhã (~07h)** manda a lista dos jogos importantes do dia: campeonato, horário de Brasília, times, estádio, onde passa e rodada.
2. **Quando TODOS os jogos do dia acabarem** manda a lista de resultados (vencedor em negrito, pênaltis, jogos adiados).

Ele roda de graça no **GitHub Actions**: não precisa de servidor nem de deixar o PC ligado.

---

## 1) Criar o bot no Telegram (2 min)
1. No Telegram, abra o **@BotFather** e mande `/newbot`.
2. Escolha um nome e um usuário (tem que terminar em `bot`, ex.: `jogosdodia_bot`).
3. Ele te dá um **TOKEN** (algo como `7123456789:AAH...`). Guarde.

## 2) Colocar o bot no grupo e pegar o ID do grupo
1. Crie o grupo (ou canal) e adicione o bot como **administrador**.
2. No grupo, mande a mensagem `/start@seu_bot` (troque pelo usuário do seu bot).
3. No navegador, abra (trocando SEU_TOKEN):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
4. Procure `"chat":{"id":-100...`. Esse número **com o sinal de menos** é o **CHAT_ID**.
   - Se aparecer vazio `[]`, mande outra mensagem no grupo e atualize a página.

> Dica: se a ideia é só o bot postar e as pessoas lerem, um **canal** fica mais limpo que um grupo. Funciona igual: adicione o bot como admin do canal e poste qualquer coisa nele para aparecer no getUpdates.

## 3) Subir os arquivos no GitHub
1. Crie uma conta em github.com (se não tiver) e clique em **New repository**.
   - Nome: `bot-futebol`. Pode ser **Public** (minutos ilimitados) ou **Private** (2.000 min/mês grátis — dá e sobra).
2. Na página do repositório: **Add file → Upload files** e arraste `bot.py`, `estado.json` e `LEIA-ME.md`. Clique **Commit changes**.
3. Agora o arquivo da automação: **Add file → Create new file**.
   - No nome, digite exatamente: `.github/workflows/bot.yml`
   - Cole o conteúdo do arquivo `bot.yml` e clique **Commit changes**.

## 4) Colocar o token e o ID (secrets)
No repositório: **Settings → Secrets and variables → Actions → New repository secret**
- Nome `TELEGRAM_TOKEN` → valor: o token do BotFather
- Nome `TELEGRAM_CHAT_ID` → valor: o número do grupo (com o `-`)

## 5) Testar agora
1. Aba **Actions** → clique em **Bot de Futebol** → **Run workflow**.
2. Em "modo" escreva `agenda` e em "forcar" escreva `sim` → **Run workflow**.
3. Em ~30 segundos a lista chega no grupo. ✅

Pronto. A partir daí ele roda sozinho a cada 30 minutos (das 07h às 03h30): manda a agenda uma vez de manhã e fica conferindo até todos os jogos acabarem para mandar os resultados uma vez só.

---

## Personalizar
- **Campeonatos**: no `bot.py`, lista `CAMPEONATOS` no topo. Apague a linha que não quiser; a ordem da lista é a ordem na mensagem. Outros códigos úteis:
  - `bra.camp.paulista` (Paulistão), `bra.camp.carioca` (Carioca), `bra.copa_do_nordeste` (Copa do Nordeste)
  - `uefa.europa.conf` (Conference League), `por.1` (Portugal), `ned.1` (Holanda)
  - `ksa.kings.cup` (Copa do Rei Saudita), `afc.champions` (Champions da Ásia)
  - `fifa.world` (Copa do Mundo), `club.friendly` (amistosos de clubes)
- **Horário da agenda**: no `bot.yml`, a primeira linha `cron` começa às `10` UTC = 07h de Brasília. Para 08h, troque `10-23` por `11-23`.
- **Textos**: as funções `montar_agenda` e `montar_resultados` no `bot.py`.

## Problemas comuns
- **Nada chegou**: aba Actions → abra a execução → veja o log do passo "Rodar o bot".
- **"chat not found"**: o CHAT_ID está errado ou o bot não está no grupo/canal.
- **Atraso de alguns minutos**: normal, o agendamento do GitHub às vezes atrasa 5–15 min.
- Os dados vêm do placar público da ESPN (grátis, sem cadastro). Não é uma API oficial, então se um dia mudar, é só me chamar que ajusto.
