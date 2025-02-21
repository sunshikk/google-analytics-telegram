import logging
import asyncio
import os
import db
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

class Form(StatesGroup): # Состояния
    waiting_website = State()
    waiting_website2 = State()
    waiting_website3 = State()
    waiting_website4 = State()

choicestart = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💬 Рассылка", callback_data="send")],
    [InlineKeyboardButton(text="✏️ Добавить другой Property ID", callback_data="otherid")],
    [InlineKeyboardButton(text="🌐 Сменить сайт", callback_data="othersite")],
    [InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="stats")]
]) # Кнопки

rassilka = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Подписаться на рассылку", callback_data="sub")],
    [InlineKeyboardButton(text="❌ Назад", callback_data="cancel")]
])

rassilka2 = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отписаться от рассылки", callback_data="unsub")],
    [InlineKeyboardButton(text="❌ Назад", callback_data="cancel")]
])

cancel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Назад", callback_data="cancel")]
])

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["TOKEN"] 

bot = Bot(token=BOT_TOKEN) # токен, который будет в качестве переменной на хостинге
dp = Dispatcher() # переменная диспетчера
router = Router() # переменная роутера
CREDENTIALS_PATH = "credentials.json"
scheduler = AsyncIOScheduler()

def check_user_exists(user_id):
    db.cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    result = db.cursor.fetchone()
    return result is not None

def show_text(username, site, website):
    return f"👋🏻 Привет, {username}!\n\n📄 Отчёт о вашем веб-сайте собирается и отправляется вам каждый день, либо по вашему запросу\n🌐 Ваш Property ID: {site}\nВаш сайт: {website}\nВы можете также сменить текущий Property ID на другой, нажав '✏️ Добавить другой Property ID'\n\n❌ Вы не подписаны на ежедневные отчеты о состоянии вашего веб-сайта. Если вы хотите получать актуальную информацию о работе вашего ресурса каждый день, вы можете подписаться на рассылку."

def show_text_two(username, site, website):
    return f"👋🏻 Привет, {username}!\n\n📄 Отчёт о вашем веб-сайте собирается и отправляется вам каждый день, либо по вашему запросу\n🌐 Ваш Property ID: {site}\nВаш сайт: {website}\nВы можете также сменить текущий Property ID на другой, нажав '✏️ Добавить другой Property ID'\n\n✅ Вы подписаны на ежедневные отчеты о состоянии вашего веб-сайта. Каждый день вы будете получать актуальную информацию о вашем веб-сайте."

def get_user_data(user_id):
    cursor = db.cursor.execute("SELECT website, site FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result

def get_all_users():
    db.cursor.execute("SELECT user_id, website, site, subscribe FROM users")
    return db.cursor.fetchall()

def get_daily_analytics(credentials_path, property_id):
    try:
        client = BetaAnalyticsDataClient.from_service_account_json(credentials_path)

        # *Изменено: Расширенный диапазон дат для отладки. Запрашиваем данные за последние 7 дней.*
        # Это поможет понять, есть ли вообще данные для этого property_id и метрик.
        date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")]

        # *Изменено: Упрощенный набор метрик для начала. Фокусируемся на базовых метриках.*
        # Если даже с ними нет данных, проблема может быть глубже.
        metrics=[
            Metric(name="totalUsers"),
            Metric(name="sessions"),
            # Metric(name="screenPageViews"),  # Временно убраны для упрощения
            # Metric(name="bounceRate"),
            # Metric(name="averageSessionDuration"),
            # Metric(name="transactions"), # Временно убраны для упрощения
        ]

        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=date_ranges,
            dimensions=[Dimension(name="date")],
            metrics=metrics,
        )
        response = client.run_report(request)

        if response.rows:
            row = response.rows[0]
            date = row.dimension_values[0].value
            metrics_data = {} # Переименовано для ясности
            for i, metric_value in enumerate(row.metric_values):
                metric_name = response.metric_headers[i].name
                metrics_data[metric_name] = metric_value.value

            return date, metrics_data
        else:
            return None, None

    except Exception as e:
        print(f"Ошибка при получении данных из Google Analytics: {e}")
        return None, None

async def send_daily_reports():
    users = get_all_users()
    for telegram_id, ga_property_id, website_url, subscribe in users:
        if subscribe:
            date, analytics_data = get_daily_analytics(CREDENTIALS_PATH, ga_property_id) # Изменено название функции и переменной
            if date and analytics_data:
                report_message = (
                    f"📊 *Ежедневная статистика для {website_url}*\n"
                    f"Дата: {date}\n\n"
                    f"📈 Пользователи: {analytics_data.get('totalUsers', 'Н/Д')}\n"
                    f"🚪 Сеансы: {analytics_data.get('sessions', 'Н/Д')}\n"
                    f"📃 Просмотры страниц: {analytics_data.get('screenPageViews', 'Н/Д')}\n"
                    f"📉 Показатель отказов: {analytics_data.get('bounceRate', 'Н/Д') or '0'}%\n" # Добавлено or '0' на случай None
                    f"⏱️ Средняя продолжительность сеанса: {int(float(analytics_data.get('averageSessionDuration', '0') or '0'))} сек.\n" # Преобразование в секунды и int
                    f"💰 Транзакции: {analytics_data.get('transactions', 'Н/Д')}\n"
                    f"💵 Выручка: ${analytics_data.get('revenue', 'Н/Д')}\n"
                )
                try:
                    await bot.send_message(telegram_id, report_message, parse_mode="Markdown")
                except Exception as e: # Обработка ошибок отправки сообщений (например, бот заблокирован)
                    logging.error(f"Ошибка отправки отчета пользователю {telegram_id}: {e}")
            else:
                logging.warning(f"Не удалось получить данные для пользователя {telegram_id} (Property ID: {ga_property_id})")

@router.message(StateFilter(None), CommandStart()) # команда /start
async def send_welcome(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    if check_user_exists(user_id):
        issub = db.cursor.execute("SELECT subscribe FROM users WHERE user_id = {}".format(user_id)).fetchone()[0]
        website = db.cursor.execute("SELECT site FROM users WHERE user_id = {}".format(user_id)).fetchone()[0]
        site_cursor = db.cursor.execute("SELECT website FROM users WHERE user_id = {}".format(user_id,))
        site = site_cursor.fetchone()
        site = site[0]
        if issub == 0:
            await message.answer(show_text(username=username, site=site, website=website), reply_markup=choicestart)
        else:
            await message.answer(show_text_two(username=username, site=site, website=website), reply_markup=choicestart)
    else:
        await message.answer(f"👋🏻 Привет, {username}!\n\n⚠️ Вы не зарегистрированы в базе данных\n🌐 Для регистрации, пожалуйста, отправьте ваш Google Analytics Property ID (например, '123456789')\n❗️ Это числовой идентификатор вашего ресурса в Google Analytics (начинается с цифры, а не 'UA-' или 'G-').")
        await state.set_state(Form.waiting_website)

@router.message(Form.waiting_website)
async def process_property_id(message: Message, state: FSMContext) -> None:
    property_id = message.text.strip()
    if not property_id.isdigit() and not (property_id.startswith("GA4-") and property_id[4:].isdigit()):
        await message.answer("❌ Неверный формат Property ID. Пожалуйста, отправьте корректный Property ID (например, `123456789` или `GA4-123456789`).")
        return
    
    await state.update_data(id=property_id)
    await state.set_state(Form.waiting_website3)
    await message.answer(f"✅ Property ID {property_id} успешно установлен!\nОтправьте ссылку на ваш сайт.")

@router.message(Form.waiting_website3)
async def process_website(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    data = await state.get_data()
    db.cursor.execute("INSERT OR IGNORE INTO users (user_id, username, website, site, subscribe) VALUES (?, ?, ?, ?, ?)", (user_id, username, data.get("id"), message.text, 1))
    db.conn.commit()
    await state.clear()
    await message.answer("✅ Веб сайт установлен.\n\nТеперь вы будете ежедневного получать отчеты о вашем сайте.")

@router.message(Form.waiting_website2)
async def process_property_id4(message: Message, state: FSMContext) -> None:
    property_id = message.text.strip()
    if not property_id.isdigit() and not (property_id.startswith("GA4-") and property_id[4:].isdigit()):
        await message.answer("❌ Неверный формат Property ID. Пожалуйста, отправьте корректный Property ID (например, `123456789` или `GA4-123456789`).")
        return

    user_id = message.from_user.id
    await state.clear()
    db.cursor.execute("UPDATE users SET website = {} WHERE user_id = {}".format(property_id, user_id))
    db.conn.commit()
    await message.answer(f"✅ Property ID {property_id} успешно сменён!")

@router.message(Form.waiting_website2)
async def process_website2(message: Message, state: FSMContext) -> None:
    property_id = message.text.strip()
    if not (property_id.startswith("https://") and not (property_id.startswith("http://"))):
        await message.answer("❌ Неверный формат ссылки. Пожалуйста, отправьте корректный формат ссылки (например: https:// , http://).")
        return

    user_id = message.from_user.id
    await state.clear()
    db.cursor.execute("UPDATE users SET site = {} WHERE user_id = {}".format(property_id, user_id))
    db.conn.commit()
    await message.answer(f"✅ Веб-сайт {property_id} успешно сменён!")

@router.callback_query() # обработка колбеков
async def process_callback(callback_query: CallbackQuery, state: FSMContext): 
    data = callback_query.data

    if data == "send":
        sub_cur = db.cursor.execute("SELECT subscribe FROM users WHERE user_id = {}".format(callback_query.from_user.id,))
        issub = sub_cur.fetchone()
        issub = issub[0]
        if issub == 1:
            await callback_query.bot.edit_message_text(
                text="💬 Рассылка\n\n✅ Вы сейчас подписаны на рассылку\n\nПреимущества рассылки:\n- 👌 Ежедневные отчёты о вашем веб-сайте\n- 📄 Сбор всей статистики вашего веб-сайта\n\n❗️ Вы можете отписаться от рассылки, нажав на кнопку ниже.",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                parse_mode=None,
                reply_markup=rassilka2
            )
        elif issub == 0:
            await callback_query.bot.edit_message_text(
                text="💬 Рассылка\n\n❌ Вы не подписаны на рассылку\n\nПреимущества рассылки:\n- 👌 Ежедневные отчёты о вашем веб-сайте\n- 📄 Сбор всей статистики вашего веб-сайта\n\n❗️ Вы можете подписаться на рассылку, нажав на кнопку ниже.",
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                parse_mode=None,
                reply_markup=rassilka
            )
    
    if data == "otherid":
        await callback_query.bot.edit_message_text(
            text="✏️ Добавление другого Property ID\n\nВведите ваш Google Analytics Property ID (например, '123456789')",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode=None,
            reply_markup=cancel
        )
        await state.set_state(Form.waiting_website2)

    if data == "sub":
        user_id = callback_query.from_user.id
        await callback_query.bot.edit_message_text(
            text="💬 Рассылка\n\n✅ Вы сейчас подписаны на рассылку\n\nПреимущества рассылки:\n- 👌 Ежедневные отчёты о вашем веб-сайте\n- 📄 Сбор всей статистики вашего веб-сайта\n\n❗️ Вы можете отписаться от рассылки, нажав на кнопку ниже.",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode=None,
            reply_markup=rassilka2
        )
        db.cursor.execute("UPDATE users SET subscribe = {} WHERE user_id = {}".format(1, user_id))
        db.conn.commit()

    if data == "unsub":
        user_id = callback_query.from_user.id
        await callback_query.bot.edit_message_text(
            text="💬 Рассылка\n\n❌ Вы не подписаны на рассылку\n\nПреимущества рассылки:\n- 👌 Ежедневные отчёты о вашем веб-сайте\n- 📄 Сбор всей статистики вашего веб-сайта\n\n❗️ Вы можете отписаться от рассылки, нажав на кнопку ниже.",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode=None,
            reply_markup=rassilka
        )
        db.cursor.execute("UPDATE users SET subscribe = {} WHERE user_id = {}".format(0, user_id))
        db.conn.commit()

    if data == "othersite":
        await callback_query.bot.edit_message_text(
            text="🌐 Смена сайта\n\nВведите ваш сайт, подключенный к Google Analytics.",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode=None,
            reply_markup=cancel
        )
        await state.set_state(Form.waiting_website4)

    if data == "stats":
        user_id = callback_query.from_user.id
        user_data = get_user_data(user_id)

        ga_property_id, website_url = user_data
        date, analytics_data = get_daily_analytics(CREDENTIALS_PATH, ga_property_id) # Изменено название функции и переменной

        if date and analytics_data:
            report_message = (
                f"📊 *Ежедневная статистика для {website_url}*\n"
                f"Дата: {date}\n\n"
                f"📈 Пользователи: {analytics_data.get('totalUsers', 'Н/Д')}\n"
                f"🚪 Сеансы: {analytics_data.get('sessions', 'Н/Д')}\n"
                f"📃 Просмотры страниц: {analytics_data.get('screenPageViews', 'Н/Д')}\n"
                f"📉 Показатель отказов: {analytics_data.get('bounceRate', 'Н/Д') or '0'}%\n" # Добавлено or '0' на случай None
                f"⏱️ Средняя продолжительность сеанса: {int(float(analytics_data.get('averageSessionDuration', '0') or '0'))} сек.\n" # Преобразование в секунды и int
                f"💰 Транзакции: {analytics_data.get('transactions', 'Н/Д')}\n"
                f"💵 Выручка: ${analytics_data.get('revenue', 'Н/Д')}\n"
            )
            await callback_query.message.answer(report_message, parse_mode="Markdown")
        else:
            await callback_query.message.answer("Не удалось получить данные статистики. Проверьте настройки и credentials.")

    if data == "cancel":
        await state.clear()
        user_id = callback_query.from_user.id
        username = callback_query.from_user.username
        sub_cur = db.cursor.execute("SELECT subscribe FROM users WHERE user_id = {}".format(user_id,))
        issub = sub_cur.fetchone()
        issub = issub[0]

        await callback_query.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if check_user_exists(user_id):
            site_cur = db.cursor.execute("SELECT website FROM users WHERE user_id = {}".format(user_id,))
            site = site_cur.fetchone()
            site = site[0]
            website = db.cursor.execute("SELECT site FROM users WHERE user_id = {}".format(user_id)).fetchone()[0]
            if issub == 0:
                await callback_query.message.answer(show_text(username=username, site=site, website=website), reply_markup=choicestart)
            else:
                await callback_query.message.answer(show_text_two(username=username, site=site, website=website), reply_markup=choicestart)

async def on_startup():
    scheduler.add_job(send_daily_reports, 'cron', hour='9', minute='0')
    scheduler.start()

async def main():
    dp.startup.register(on_startup)
    dp.include_router(router) # инициализация роутера
    await dp.start_polling(bot) # запуск бота

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO) # инициализация логгера
    try:
        asyncio.run(main()) # запускаем функцию main в асинхронном режиме
    except KeyboardInterrupt:
        print('Бот выключен')
