import os
os.environ['ORT_DISABLE_GPU'] = '1'  # Desativa completamente tentativas de usar GPU
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Silencia logs desnecessários

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
from rembg import remove, new_session
from PIL import Image
import io
import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Dict, Optional

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = 'Seu_TOKEN_aqui'
MAX_CONCURRENT_JOBS = 2  # Reduzido para melhor desempenho em CPU

# Modelos otimizados para CPU
MODELS = {
    'auto': 'u2net',
    'pessoas': 'u2net_human_seg',
    'produtos': 'u2netp',
    'animais': 'u2net_cloth_seg'
}

# Mensagens do bot
MESSAGES = {
    'start': "👋 Olá! Envie uma imagem para remover o fundo. Use /help para ajuda.",
    'help': "📚 Envie fotos ou imagens como documento para remover o fundo automaticamente.",
    'queue': "📊 Sua imagem está na posição {} da fila\n⏳ Tempo estimado: {} segundos",
    'processing': "🔄 Processando sua imagem...",
    'success': "✅ Fundo removido com sucesso!",
    'error': "❌ Erro ao processar. Tente novamente.",
    'no_image': "⚠️ Por favor, envie uma imagem válida (foto ou documento)"
}

# Sistema de fila global
job_queue = deque()
current_jobs: Dict[int, asyncio.Task] = {}

# Sessões pré-carregadas (otimizado para CPU)
sessions = {
    model: new_session(model, providers=['CPUExecutionProvider'])
    for model in MODELS.values()
}

class ProcessingJob:
    def __init__(self, update: Update, file_bytes: bytes, file_id: str):
        self.update = update
        self.file_bytes = file_bytes
        self.file_id = file_id
        self.model = MODELS['auto']
        self.status_message = None

    async def send_queue_position(self, position: int):
        """Envia mensagem com posição na fila"""
        wait_time = position * 30  # Estimativa mais conservadora para CPU
        try:
            self.status_message = await self.update.message.reply_text(
                MESSAGES['queue'].format(position, wait_time),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🖼️ Mudar Modelo", callback_data=f"model_{self.file_id}")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{self.file_id}")]
                ])
            )
        except Exception as e:
            logger.error(f"Erro ao enviar posição na fila: {str(e)}")

    async def update_status(self, text: str):
        """Atualiza a mensagem de status"""
        if self.status_message:
            try:
                await self.status_message.edit_text(text)
            except Exception as e:
                logger.warning(f"Não foi possível atualizar mensagem: {str(e)}")
                # Tenta enviar uma nova mensagem se não conseguir editar
                self.status_message = await self.update.message.reply_text(text)

    async def process(self):
        """Executa o processamento da imagem"""
        try:
            await self.update_status(MESSAGES['processing'])

            # Processamento com o modelo selecionado
            processed_bytes = remove(
                self.file_bytes,
                session=sessions[self.model]
            )

            # Salva e envia o resultado
            with Image.open(io.BytesIO(processed_bytes)) as img:
                with io.BytesIO() as output:
                    img.save(output, format='PNG', optimize=True)
                    output.seek(0)
                    await self.update.message.reply_document(
                        document=output,
                        filename=f"sem_fundo_{self.file_id[:8]}.png",
                        caption=MESSAGES['success']
                    )

            logger.info(f"Job {self.file_id} concluído com sucesso")

        except Exception as e:
            logger.error(f"Erro no job {self.file_id}: {str(e)}")
            await self.update_status(MESSAGES['error'])
            await self.update.message.reply_text(
                "⚠️ Ocorreu um erro durante o processamento. Por favor, tente novamente."
            )

async def process_queue():
    """Processa itens da fila de forma otimizada para CPU"""
    while job_queue and len(current_jobs) < MAX_CONCURRENT_JOBS:
        job = job_queue.popleft()
        task = asyncio.create_task(job.process())
        current_jobs[id(job)] = task
        task.add_done_callback(lambda t, j=id(job): current_jobs.pop(j))

async def handle_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe e processa imagens"""
    try:
        file = await get_image_file(update, context)
        if not file:
            await update.message.reply_text(MESSAGES['no_image'])
            return

        file_bytes = await file.download_as_bytearray()
        job = ProcessingJob(update, bytes(file_bytes), file.file_id)
        job_queue.append(job)
        
        position = len(job_queue) + len(current_jobs) - 1
        await job.send_queue_position(position)
        
        if len(current_jobs) < MAX_CONCURRENT_JOBS:
            await process_queue()

    except Exception as e:
        logger.error(f"Erro ao receber imagem: {str(e)}")
        await update.message.reply_text(MESSAGES['error'])

async def get_image_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[object]:
    """Obtém o arquivo de imagem da mensagem"""
    try:
        if update.message.photo:
            return await context.bot.get_file(update.message.photo[-1].file_id)
        elif update.message.document:
            # Verifica se é uma imagem pelo mime type
            mime_type = update.message.document.mime_type
            if mime_type and mime_type.startswith('image/'):
                return await context.bot.get_file(update.message.document.file_id)
        return None
    except Exception as e:
        logger.error(f"Erro ao obter arquivo: {str(e)}")
        return None

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia interações dos botões inline"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, file_id = query.data.split('_', 1)
        job = next((j for j in list(job_queue) if j.file_id == file_id), None)
        
        if not job:
            await query.edit_message_text("⚠️ Esta imagem já foi processada ou cancelada")
            return
        
        if action == 'model':
            keyboard = [
                [InlineKeyboardButton(f"🤖 {name}", callback_data=f"setmodel_{file_id}_{model}")]
                for name, model in MODELS.items()
            ]
            await query.edit_message_text(
                "🛠️ Selecione o modelo de IA:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif action.startswith('setmodel'):
            _, _, model = query.data.split('_')
            job.model = model
            await query.edit_message_text(f"✅ Modelo definido como: {model}")
        
        elif action == 'cancel':
            job_queue.remove(job)
            await query.edit_message_text("❌ Processamento cancelado")
    
    except Exception as e:
        logger.error(f"Erro no handler de botões: {str(e)}")
        await query.edit_message_text("⚠️ Ocorreu um erro ao processar sua solicitação")

async def periodic_queue_check(context: ContextTypes.DEFAULT_TYPE):
    """Verificação periódica da fila"""
    await process_queue()

def main():
    """Função principal para iniciar o bot"""
    try:
        # Verifica dependências essenciais
        try:
            import onnxruntime
            from telegram.ext import JobQueue
        except ImportError as e:
            logger.error(f"Erro nas dependências: {str(e)}")
            print("\n⚠️ Instale as dependências corretamente:")
            print('pip install "python-telegram-bot[job-queue]" rembg onnxruntime pillow')
            return

        # Configura a aplicação
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text(MESSAGES['start'])))
        app.add_handler(CommandHandler("help", lambda u,c: u.message.reply_text(MESSAGES['help'])))
        app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_images))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        # Configura o processamento periódico
        job_queue = app.job_queue
        if job_queue:
            job_queue.run_repeating(periodic_queue_check, interval=5.0)
        else:
            logger.warning("JobQueue não disponível - usando fallback")
            asyncio.create_task(periodic_queue_check(None))
        
        logger.info("Bot iniciado com sucesso")
        app.run_polling()
    
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}")
        raise

if __name__ == "__main__":
    print("✅ Iniciando bot de remoção de fundos...")
    main()
