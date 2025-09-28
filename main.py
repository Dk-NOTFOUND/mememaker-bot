import os
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from PIL import Image, ImageDraw, ImageFont
import textwrap

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Состояния FSM
class TextState(StatesGroup):
    waiting_for_text = State()
    waiting_for_color = State()
    waiting_for_size = State()


# Функции для обработки изображений (аналогичные предыдущим)
def wrap_text(text, font, max_width):
    """Переносит текст так, чтобы он помещался в указанную ширину"""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        try:
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
        except:
            line_width = ImageDraw.Draw(Image.new('RGB', (1, 1))).textsize(test_line, font=font)[0]

        if line_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))

    if not lines:
        lines = [text]

    final_lines = []
    for line in lines:
        try:
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
        except:
            line_width = ImageDraw.Draw(Image.new('RGB', (1, 1))).textsize(line, font=font)[0]

        if line_width <= max_width:
            final_lines.append(line)
        else:
            chars_per_line = len(line) * max_width // line_width
            wrapped = textwrap.fill(line, width=chars_per_line)
            final_lines.extend(wrapped.split('\n'))

    return final_lines


def calculate_text_position(image_width, image_height, text_block_width, text_block_height):
    """Вычисляет позицию текста в середине нижней трети изображения"""
    lower_third_y = image_height * 2 // 3
    x = (image_width - text_block_width) // 2
    y = lower_third_y + (image_height - lower_third_y - text_block_height) // 2
    return (x, y)


async def process_image_with_text(image_bytes, text, color=(255, 255, 255), font_size=60):
    """Обрабатывает изображение и добавляет текст"""
    try:
        # Открываем изображение из байтов
        image = Image.open(BytesIO(image_bytes))
        draw = ImageDraw.Draw(image)

        # Загружаем шрифт
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeMono.ttf", font_size)
            except:
                font = ImageFont.load_default()

        # Определяем максимальную ширину для текста (80% ширины изображения)
        max_text_width = int(image.width * 0.9)

        # Разбиваем текст на строки
        lines = wrap_text(text, font, max_text_width)

        # Вычисляем общую высоту текстового блока
        try:
            bbox = draw.textbbox((0, 0), "Test", font=font)
            line_height = bbox[3] - bbox[1]
        except:
            line_height = draw.textsize("Test", font=font)[1]

        total_text_height = line_height * len(lines)

        # Вычисляем ширину самой широкой строки
        max_line_width = 0
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = draw.textsize(line, font=font)[0]

            if line_width > max_line_width:
                max_line_width = line_width

        # Вычисляем позицию для всего текстового блока
        position = calculate_text_position(
            image.width, image.height, max_line_width, total_text_height
        )

        # Добавляем черную обводку для лучшей читаемости
        outline_width = 2
        for i, line in enumerate(lines):
            line_y = position[1] + i * line_height

            # Вычисляем позицию для текущей строки (центрируем)
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
            except:
                line_width = draw.textsize(line, font=font)[0]

            line_x = position[0] + (max_line_width - line_width) // 2

            # Обводка
            for dx in [-outline_width, 0, outline_width]:
                for dy in [-outline_width, 0, outline_width]:
                    if dx != 0 or dy != 0:
                        outline_pos = (line_x + dx, line_y + dy)
                        draw.text(outline_pos, line, fill=(0, 0, 0), font=font)

            # Основной текст
            draw.text((line_x, line_y), line, fill=color, font=font)

        # Сохраняем изображение в буфер
        output_buffer = BytesIO()
        image.save(output_buffer, format="JPEG")
        output_buffer.seek(0)

        return output_buffer

    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        return None


# Обработчики команд и сообщений
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для добавления текста на фото.\n\n"
        "Просто отправь мне фото, а затем введи текст, который хочешь добавить."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Как пользоваться ботом:\n"
        "1. Отправь фото (как сжатое изображение или документ)\n"
        "2. Введи текст, который хочешь добавить на фото\n"
        "3. Бот обработает изображение и вернет результат"
    )


@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Обработка фото"""
    # Сохраняем информацию о фото
    photo = message.photo[-1]  # Берем фото наивысшего качества
    file_id = photo.file_id

    await state.update_data(photo_file_id=file_id)
    await state.set_state(TextState.waiting_for_text)

    await message.answer(
        "Фото получено! Теперь введи текст, который хочешь добавить на изображение.\n\n"
        "Если нужно отменить операцию, используй команду /cancel"
    )


@dp.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    """Обработка документов (например, несжатых изображений)"""
    document = message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        # Сохраняем информацию о документе
        file_id = document.file_id

        await state.update_data(photo_file_id=file_id)
        await state.set_state(TextState.waiting_for_text)

        await message.answer(
            "Изображение получено! Теперь введи текст, который хочешь добавить.\n\n"
            "Если нужно отменить операцию, используй команду /cancel"
        )
    else:
        await message.answer("Пожалуйста, отправьте изображение.")


@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "отмена")
async def cancel_handler(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных операций для отмены.")
        return

    await state.clear()
    await message.answer("Операция отменена.")


@dp.message(TextState.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    """Обработка текста от пользователя"""
    text = message.text.strip()

    if not text:
        await message.answer("Пожалуйста, введите текст.")
        return

    # Получаем file_id фото из состояния
    user_data = await state.get_data()
    file_id = user_data.get('photo_file_id')

    if not file_id:
        await message.answer("Не удалось найти фото. Пожалуйста, отправьте фото заново.")
        await state.clear()
        return

    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer("Обрабатываю изображение...")

    try:
        # Скачиваем фото
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Обрабатываем изображение
        image_data = file_bytes.read()
        result_buffer = await process_image_with_text(image_data, text)

        if result_buffer:
            # Создаем объект для отправки
            input_file = BufferedInputFile(result_buffer.read(), filename="image_with_text.jpg")

            # Отправляем результат
            await message.answer_photo(
                input_file,
                caption="Ваше изображение с текстом готово!"
            )
        else:
            await message.answer("Произошла ошибка при обработке изображения. Попробуйте еще раз.")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка. Попробуйте еще раз.")

    finally:
        # Очищаем состояние
        await state.clear()
        # Удаляем сообщение о обработке
        try:
            await bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass


@dp.message()
async def other_messages(message: Message):
    """Обработка прочих сообщений"""
    await message.answer(
        "Отправьте мне фото, чтобы добавить на него текст.\n"
        "Используйте /help для получения справки."
    )


# Запуск бота
async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())