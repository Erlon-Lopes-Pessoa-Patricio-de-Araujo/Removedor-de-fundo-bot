# Bot Telegram - Remoção de Fundo de Imagens

Este projeto é um bot para Telegram que remove o fundo de imagens automaticamente usando IA. O bot aceita fotos ou imagens enviadas como documento, processa em fila e retorna o arquivo com fundo transparente.

## Funcionalidades

- Remoção automática de fundo de imagens (PNG/JPG)
- Suporte a diferentes modelos de IA para pessoas, produtos, animais, etc.
- Fila de processamento com limite de jobs simultâneos (CPU)
- Escolha do modelo de IA via botões inline
- Cancelamento de jobs na fila
- Código em Python com [python-telegram-bot](https://python-telegram-bot.org/) e [rembg](https://github.com/danielgatis/rembg)

## Como usar

1. **Clone o repositório:**
   ```sh
   git clone https://github.com/seu-usuario/seu-repo.git
   cd seu-repo
   ```

2. **Instale as dependências:**
   ```sh
   pip install "python-telegram-bot[job-queue]" rembg onnxruntime pillow
   ```

3. **Configure o token do bot:**
   - Edite o arquivo `teste telegram V2.py` e coloque o seu token do Bot Telegram na variável `TOKEN`.

4. **Execute o bot:**
   ```sh
   python "teste telegram V2.py"
   ```

5. **No Telegram:**
   - Envie uma imagem ou foto para o bot.
   - Aguarde o processamento e receba o arquivo sem fundo.

## Modelos suportados

- `auto` (padrão)
- `pessoas`
- `produtos`
- `animais`

Você pode escolher o modelo clicando em "Mudar Modelo" enquanto sua imagem está na fila.

## Observações

- O bot processa até 2 imagens ao mesmo tempo (ajustável em `MAX_CONCURRENT_JOBS`).
- O processamento é feito apenas em CPU para máxima compatibilidade.
- Não compartilhe seu token do bot publicamente.

## Licença

Este projeto é livre para uso pessoal e educacional. Para uso comercial, consulte as licenças das bibliotecas utilizadas.

---

Feito por Erlon Lopes
