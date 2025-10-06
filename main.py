import telebot
import aiohttp
import asyncio
import json
from telebot import types, TeleBot
import requests
import random
from collections import defaultdict
import time
import os
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PROXY_API_KEY = os.getenv('PROXY_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}
user_answers = {}
bad_prompts = {}
welcome_message_sent = {}
user_reset_time = {}
user_requests = defaultdict(int)
user_gpt_requests = defaultdict(int) 
MAX_GPT_REQUESTS = 10  

RESET_TIME = 9999999999999999999


def save_user_data(user_data):
    try:
        
        if not os.path.exists('user_data'):
            os.makedirs('user_data')
        filename = f"user_data/{user_data['email'].replace('@', '_at_').replace('.', '_dot_')}.json"
        
        user_data['registered_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)
        all_users_file = 'user_data/all_users.json'
        all_users = []
        if os.path.exists(all_users_file):
            with open(all_users_file, 'r', encoding='utf-8') as f:
                try:
                    all_users = json.load(f)
                except json.JSONDecodeError:
                    all_users = []
        all_users.append(user_data)
        with open(all_users_file, 'w', encoding='utf-8') as f:
            json.dump(all_users, f, ensure_ascii=False, indent=4)
        
        return True
    except Exception as e:
        print(f"Ошибка при сохранении данных пользователя: {str(e)}")
        return False

def save_log_to_file(log_data):
    try:
        if not os.path.exists('logs'):
            os.makedirs('logs')
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = f"logs/auth_logs_{current_date}.txt"
        log_message = f"[{log_data['timestamp']}] {log_data['message']}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)
        
        return True
    except Exception as e:
        print(f"Ошибка при сохранении лога: {str(e)}")
        return False


@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = message.web_app_data.data
        user_id = message.from_user.id
        username = message.from_user.username or "Нет username"
        name = message.from_user.full_name or "Нет имени"
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'message': f"Получены данные от пользователя {user_id} ({username}): {data}"
        }
        save_log_to_file(log_data)
        
        print(f"Получены данные от веб-приложения: {data}")
        
        if data.startswith('register:'):
            _, email, password = data.split(':')
            user_data = {
                'telegram_id': user_id,
                'telegram_username': username,
                'name': name,
                'email': email,
                'password': password
            }
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'message': f"Регистрация пользователя: {email} (Telegram ID: {user_id})"
            }
            save_log_to_file(log_data)
            
            if save_user_data(user_data):
                bot.send_message(message.chat.id, "Регистрация успешно завершена!")
                bot.answer_web_app_query(
                    message.web_app_data.query_id,
                    "Регистрация успешно завершена!"
                )
            else:
                bot.send_message(message.chat.id, "Ошибка при регистрации. Пожалуйста, попробуйте позже.")
                bot.answer_web_app_query(
                    message.web_app_data.query_id,
                    "Ошибка при регистрации. Пожалуйста, попробуйте позже."
                )
        
        elif data.startswith('login:'):
            _, email, password = data.split(':')
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'message': f"Попытка входа: {email} (Telegram ID: {user_id})"
            }
            save_log_to_file(log_data)
            user_file = f"user_data/{email.replace('@', '_at_').replace('.', '_dot_')}.json"
            
            if os.path.exists(user_file):
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                if user_data.get('password') == password:
                    bot.send_message(message.chat.id, "Вход выполнен успешно!")
                    bot.answer_web_app_query(
                        message.web_app_data.query_id,
                        "Вход выполнен успешно!"
                    )
                    log_data = {
                        'timestamp': datetime.now().isoformat(),
                        'message': f"Успешный вход: {email} (Telegram ID: {user_id})"
                    }
                    save_log_to_file(log_data)
                else:
                    bot.send_message(message.chat.id, "Неверный пароль.")
                    bot.answer_web_app_query(
                        message.web_app_data.query_id,
                        "Неверный пароль."
                    )
                    log_data = {
                        'timestamp': datetime.now().isoformat(),
                        'message': f"Неверный пароль при входе: {email} (Telegram ID: {user_id})"
                    }
                    save_log_to_file(log_data)
            else:
                bot.send_message(message.chat.id, "Пользователь с таким email не найден.")
                bot.answer_web_app_query(
                    message.web_app_data.query_id,
                    "Пользователь с таким email не найден."
                )
                log_data = {
                    'timestamp': datetime.now().isoformat(),
                    'message': f"Пользователь не найден: {email} (Telegram ID: {user_id})"
                }
                save_log_to_file(log_data)
    except Exception as e:
        print(f"Ошибка при обработке данных веб-приложения: {str(e)}")
        bot.send_message(message.chat.id, "Произошла ошибка при обработке данных.")
        if hasattr(message, 'web_app_data') and hasattr(message.web_app_data, 'query_id'):
            bot.answer_web_app_query(
                message.web_app_data.query_id,
                "Произошла ошибка при обработке данных."
            )
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'message': f"Ошибка при обработке данных: {str(e)}"
        }
        save_log_to_file(log_data)

@bot.message_handler(commands=['start'])
def main(message):
    user_id = message.from_user.id
    user_states[user_id] = 'main_menu'
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Ознакомление с курсом')
    btn2 = types.KeyboardButton('Задания')                  
    btn3 = types.KeyboardButton('Тренировка')
    btn4 = types.KeyboardButton('Оценка промпта')

    web_app = types.WebAppInfo(url="https://lunarcelestia.github.io/GPTuchit_store/")  #
    btn_web_app = types.KeyboardButton(text="Курсы", web_app=web_app)
    
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    markup.row(btn_web_app)
    
    bot.send_message(message.chat.id, f'Привет, {message.from_user.full_name}! Это бот, который поможет тебе выучить как правильно пользоваться чатом GPT! \n' +
                     "Также вы можете приобрести наши расширенные курсы, которые помогут вам освоить искусство создания эффективных промптов. \n" +
                     "Для ознакомления перейдите в наше мини-приложение, нажав на кнопку в меню 'Курсы' ", reply_markup=markup)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'main_menu')
def handle_main_menu(message):
    if message.text == 'Ознакомление с курсом':
        bot.send_message(message.chat.id, '''В эпоху развития искусственного интеллекта умение эффективно взаимодействовать с большими языковыми моделями LLM становится ключевым навыком. Промпт-инжиниринг это искусство и наука создания запросов (промптов), которые позволяют LLM генерировать желаемые, точные и полезные результаты"". Почему это важно: "Независимо от вашей профессии маркетинг, разработка, образование или даже наука, владение промпт-инжинирингом открывает новые возможности для автоматизации задач, генерации контента и решения сложных проблем". "Без грамотного подхода к составлению промптов, даже самые мощные LLM могут выдавать неточные, нерелевантные или даже нежелательные ответы"''')
    elif message.text == 'Задания':
        user_states[message.from_user.id] = 'tasks'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Задание 1')
        btn2 = types.KeyboardButton('Задание 2')
        btn3 = types.KeyboardButton('Задание 3')
        btn4 = types.KeyboardButton('Задание 4')
        btn5 = types.KeyboardButton('Задание 5')
        btn6 = types.KeyboardButton('Задание 6')
        btn7 = types.KeyboardButton('Задание 7')
        btn8 = types.KeyboardButton('Задание 8')
        btn9 = types.KeyboardButton('Задание 9')
        btn10 = types.KeyboardButton('Задание 10')
        btn11 = types.KeyboardButton('Задание 11')
        btn12 = types.KeyboardButton('Задание 12')
        btn13 = types.KeyboardButton('Задание 13')
        btn14 = types.KeyboardButton('Задание 14')
        btn15 = types.KeyboardButton('Задание 15')
        btn16 = types.KeyboardButton('Задание 16')
        btn17 = types.KeyboardButton('Задание 17')
        btn18 = types.KeyboardButton('Задание 18')
        btn19 = types.KeyboardButton('Задание 19')
        btn20 = types.KeyboardButton('Задание 20')
        btn21 = types.KeyboardButton('Задание 21')
        btn22 = types.KeyboardButton('Задание 22')
        btn23 = types.KeyboardButton('Задание 23')
        btn24 = types.KeyboardButton('Задание 24')
        btn25 = types.KeyboardButton('Задание 25')
        btn26 = types.KeyboardButton('Задание 26')
        btn27 = types.KeyboardButton('Задание 27')
        btn28 = types.KeyboardButton('Задание 28')
        btn29 = types.KeyboardButton('Задание 29')
        btn30 = types.KeyboardButton('Задание 30')
        btn31 = types.KeyboardButton('Вернуться в главное меню')
        markup.row(btn1, btn2, btn3)
        markup.row(btn4, btn5, btn6)
        markup.row(btn7, btn8, btn9)
        markup.row(btn10, btn11, btn12)
        markup.row(btn13, btn14, btn15)
        markup.row(btn16, btn17, btn18)
        markup.row(btn19, btn20, btn21)
        markup.row(btn22, btn23, btn24)
        markup.row(btn25, btn26, btn27)
        markup.row(btn28, btn29, btn30)
        markup.row(btn31)
        bot.send_message(message.chat.id, 'Выберите задание:', reply_markup=markup)
    elif message.text == 'Тренировка':
        start_training(message.chat.id)
    elif message.text == 'Оценка промпта':
        asyncio.run(handle_prompt_evaluation(message.chat.id))


def start_training(chat_id):
    if user_gpt_requests[chat_id] >= MAX_GPT_REQUESTS:
        bot.send_message(chat_id, "Ваши запросы к GPT закончились. Лимит: 10 запросов.")
        return_to_main_menu(bot.get_message(chat_id))
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_return = types.KeyboardButton('Вернуться в главное меню')
    markup.add(btn_return)
    bot.send_message(chat_id, "Введите ваш промпт на любую тему, и я оценю его качество.", reply_markup=markup)
    user_states[chat_id] = 'waiting_for_prompt_response'

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'waiting_for_prompt_response')
def handle_prompt_response(message):
    try:
        user_id = message.from_user.id
        user_prompt = message.text

        if user_prompt == 'Вернуться в главное меню':
            return_to_main_menu(message)
            return

        if user_gpt_requests[user_id] >= MAX_GPT_REQUESTS:
            bot.send_message(message.chat.id, "Ваши запросы к GPT закончились. Лимит: 10 запросов.")
            return_to_main_menu(message)
            return

        formatted_prompt = f"Оцени качество следующего промпта и дай советы по его улучшению: '{user_prompt}'"
        response = asyncio.run(get_openai_response(formatted_prompt, user_id))
        
        if response is None:
            remaining_requests = MAX_GPT_REQUESTS - user_gpt_requests[user_id]
            bot.send_message(message.chat.id, f"У вас осталось {remaining_requests} запросов.")
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn_return = types.KeyboardButton('Вернуться в главное меню')
            markup.add(btn_return)
            bot.send_message(message.chat.id, "Можете отправить следующий промпт или вернуться в главное меню", reply_markup=markup)
            return
            
        if response.startswith("Ваши запросы к GPT закончились"):
            bot.send_message(message.chat.id, response)
            return_to_main_menu(message)
            return
            
        # ответ к GPT
        bot.send_message(message.chat.id, response)
        
        # счетчик запросов
        remaining_requests = MAX_GPT_REQUESTS - user_gpt_requests[user_id]
        bot.send_message(message.chat.id, f"У вас осталось {remaining_requests} запросов.")
        
        # и некст предложение кинуть промпт
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_return = types.KeyboardButton('Вернуться в главное меню')
        markup.add(btn_return)
        bot.send_message(message.chat.id, "Можете отправить следующий промпт или вернуться в главное меню", reply_markup=markup)
        
        user_states[user_id] = 'waiting_for_prompt_response'
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при обработке запроса. Попробуйте еще раз.")
        print(f"Error in handle_prompt_response: {str(e)}")

async def get_openai_response(prompt, user_id=None):
    try:
        if user_id is not None:
            if user_gpt_requests[user_id] >= MAX_GPT_REQUESTS:
                return "Ваши запросы к GPT закончились. Лимит: 10 запросов."
            
            user_gpt_requests[user_id] += 1
            processing_message = bot.send_message(user_id, "Chat GPT обрабатывает запрос...")

        request_url = "https://api.proxyapi.ru/openai/v1/chat/completions"
        model = "gpt-4-turbo-preview"

        headers = {
            "Authorization": f"Bearer {PROXY_API_KEY}",
            "Content-Type": "application/json"
        }

        request_body = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 1024
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(request_url, headers=headers, json=request_body) as response:
                if response.status == 200:
                    response_json = await response.json()
                    if "choices" in response_json and len(response_json["choices"]) > 0:
                        gpt_response = response_json["choices"][0]["message"]["content"]
                        # Редактируем сообщение о обработке на ответ от GPT
                        if user_id is not None:
                            bot.edit_message_text(chat_id=user_id, message_id=processing_message.message_id, text=gpt_response)
                            return None  # Возвращаем None
                        return gpt_response
                    else:
                        error_text = "Ошибка: Нет ответа от OpenAI."
                        if user_id is not None:
                            bot.edit_message_text(chat_id=user_id, message_id=processing_message.message_id, text=error_text)
                            return None
                        return error_text
                else:
                    error_text = f"Ошибка: {response.status} - {await response.text()}"
                    if user_id is not None:
                        bot.edit_message_text(chat_id=user_id, message_id=processing_message.message_id, text=error_text)
                        return None
                    return error_text
    except Exception as e:
        error_text = f"Произошла ошибка при обработке запроса: {str(e)}"
        if user_id is not None:
            bot.edit_message_text(chat_id=user_id, message_id=processing_message.message_id, text=error_text)
            return None
        return error_text

async def generate_bad_prompt(user_id):
    try:
        request_url = "https://api.proxyapi.ru/openai/v1/chat/completions"
        model = "gpt-4-turbo-preview"

        headers = {
            "Authorization": f"Bearer {PROXY_API_KEY}",
            "Content-Type": "application/json"
        }

        request_body = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Придумай плохой промпт с грамматическими ошибками и неясными формулировками и прочими любыми неясностями, только в самом сообщении сами ошибки не озвучивай, сам знай их и только."}
            ],
            "temperature": 0.5,
            "max_tokens": 1024
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(request_url, headers=headers, json=request_body) as response:
                if response.status == 200:
                    response_json = await response.json()
                    if "choices" in response_json and len(response_json["choices"]) > 0:
                        return response_json["choices"][0]["message"]["content"]
                    else:
                        return "Ошибка: Нет ответа от OpenAI."
                else:
                    return f"Ошибка: {response.status} - {await response.text()}"
    except Exception as e:
        print(f"Error in generate_bad_prompt: {str(e)}")
        return "Произошла ошибка при генерации промпта. Попробуйте еще раз."

async def handle_prompt_evaluation(chat_id):
    bot.send_message(chat_id, "Добро пожаловать в раздел 'Оценка промпта'! Здесь вы сможете оценить качество промпта, который будет сгенерирован, а после этого проверить, насколько точно вы охарактеризовали данный промпт.")
    welcome_message_sent[chat_id] = True
    
    prompt = await generate_bad_prompt(chat_id)
    if prompt.startswith("Ошибка"):
        bot.send_message(chat_id, prompt)
        return_to_main_menu(bot.get_message(chat_id))
        return
        
    bad_prompts[chat_id] = prompt 
    bot.send_message(chat_id, f"Промпт для оценки: {prompt}\n\nВаше мнение об этом промпте:")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_return = types.KeyboardButton('Вернуться в главное меню')
    markup.add(btn_return)
    bot.send_message(chat_id, "Введите ваш ответ или нажмите 'Вернуться в главное меню'", reply_markup=markup)
    user_states[chat_id] = 'waiting_for_feedback'

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'waiting_for_feedback')
def handle_user_feedback(message):
    user_id = message.from_user.id
    user_feedback = message.text

    if user_feedback == 'Вернуться в главное меню':
        return_to_main_menu(message)
        return
    if user_gpt_requests[user_id] >= MAX_GPT_REQUESTS:
        bot.send_message(message.chat.id, "Ваши запросы к GPT закончились. Лимит: 10 запросов.")
        return_to_main_menu(message)
        return
    
    prompt = bad_prompts.get(user_id, "")
    if not prompt:
        bot.send_message(message.chat.id, "Не удалось найти плохой промпт для анализа.")
        return

    analysis = asyncio.run(get_openai_response(f"Пользователь оценил промпт: '{prompt}'. Его мнение: '{user_feedback}'. Проанализируй это и укажи, где пользователь прав, а где не заметил ошибки. Также сам дай общую краткую оценку этому промпту.", user_id))
    
    if analysis.startswith("Ваши запросы к GPT закончились"):
        bot.send_message(message.chat.id, analysis)
        return_to_main_menu(message)
        return
    bot.send_message(message.chat.id, f"Анализ от GPT: {analysis}")
    

    remaining_requests = MAX_GPT_REQUESTS - user_gpt_requests[user_id]
    bot.send_message(message.chat.id, f"У вас осталось {remaining_requests} запросов.")
    

    user_states[user_id] = 'main_menu' 
    bot.send_message(message.chat.id, "Вы вернулись в главное меню!")


def generate_tasks_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(1, 31, 3):
        row = [types.KeyboardButton(f'Задание {j}') for j in range(i, min(i+3, 31))]
        markup.row(*row)
    markup.row(types.KeyboardButton('Вернуться в главное меню'))
    return markup
    

def handle_tasks(message):
    tasks = {
        'Задание 1': ("""Исходный промпт: Напиши стихотворение о кошке.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши стихотворение в стиле хайку о черной кошке, спящей на солнечном подоконнике.

B: Напиши красивое стихотворение про кошку.

C: Напиши короткое стихотворение о кошке.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_1'),
        'Задание 2': ("""Исходный промпт: Напиши пост для социальных сетей о полезных свойствах яблок.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши короткий пост о пользе яблок.

B: Напиши пост, в котором перечисли все витамины в яблоках.

C: Напиши пост в стиле Instagram для подростков, рассказывающий о том, как яблоки помогают бороться с акне и поддерживать энергию в течение дня. Используй хэштеги #здороваякожа #яблочныйперекус #энергиянадень.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_2'),
        'Задание 3': ("""Исходный промпт: Сгенерируй идею для приложения.

Вопрос: Какой из этих промптов даст более качественный результат? 

A: Сгенерируй интересную идею для приложения.

B: Сгенерируй идею для мобильного приложения, которое поможет людям отслеживать и улучшать свои привычки сна. Приложение должно включать функции будильника, ведения журнала сновидений и образовательные статьи о гигиене сна.

C: Сгенерируй идею для приложения, связанного со здоровьем.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_3'),
        'Задание 4': ("""Исходный промпт: Объясни, что такое квантовая физика.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Объясни, что такое квантовая физика.

B: Объясни квантовую физику с помощью формул.

C: Объясни, что такое квантовая физика, для пятилетнего ребенка, используя простые примеры и аналоги. Избегай сложной терминологии.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_4'),
        'Задание 5': ("""Исходный промпт: Напиши письмо в службу поддержки клиентов.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши письмо в службу поддержки.

B: Напиши вежливое и профессиональное письмо в службу поддержки клиентов, жалуясь на неисправный товар (укажи конкретный товар и номер заказа). Опиши проблему подробно и попроси вернуть деньги.

C: Напиши гневное письмо в службу поддержки.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_5'),
        'Задание 6': ("""Исходный промпт: Напиши эссе о природе.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши короткое эссе о природе.

B: Напиши эссе о влиянии изменения климата на экосистемы тропических лесов.

C: Напиши эссе о природе.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_6'),
        'Задание 7': ("""Исходный промпт: Напиши стихотворение о любви.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши стихотворение о первой любви, полное нежности и воспоминаний о беззаботных днях.

B: Напиши стихотворение о любви.

C: Напиши короткое стихотворение о любви.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_7'),
        'Задание 8': ("""Исходный промпт: Напиши рассказ о дружбе.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши короткий рассказ о дружбе.

B: Напиши рассказ о том, как двое друзей преодолевают трудности и поддерживают друг друга в сложные времена.

C: Напиши рассказ о дружбе.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_8'),
        'Задание 9': ("""Исходный промпт: Напиши инструкцию по приготовлению блюда.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши инструкцию по приготовлению блюда.

B: Напиши инструкцию по приготовлению пасты с соусом песто и курицей.

C: Напиши короткую инструкцию по приготовлению блюда.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_9'),
        'Задание 10': ("""Исходный промпт: Напиши рассказ о детях на празднике.

Вопрос: Какой из этих промптов даст более качественный результат?
                       
A: Напиши рассказ о детях, радостно играющих на день рождения с воздушными шариками и тортом.

B: Напиши рассказ о детях на празднике.

C: Напиши рассказ о празднике, где играют дети.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_10'),
        'Задание 11': ("""Исходный промпт: Напиши описание осеннего леса.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши о лесу осенью.

C: Опиши лес в осеннюю пору.

B: Опиши осенний лес, где золотые листья падают на землю, а воздух свежий и прохладный.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_11'),
        'Задание 12': ("""Исходный промпт: Напиши рассказ о детях, играющих во дворе.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши рассказ о детях, играющих во дворе.

B: Напиши рассказ о группе детей, играющих в прятки в жаркий летний день во дворе, полном укромных мест.

C: Напиши короткий рассказ о детских играх.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_12'),
        'Задание 13': ("""Исходный промпт: Напиши эссе о музыке.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши эссе о музыке.

B: Напиши эссе о влиянии классической музыки на эмоциональное состояние и восприятие человека.

C: Напиши короткое эссе о разных жанрах музыки.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_13'),
        'Задание 14': ("""Исходный промпт: Напиши стихотворение о зиме.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши стихотворение о морозном зимнем утре, когда снег тихо падает на пустынные улицы города.

B: Напиши стихотворение о зиме.

C: Напиши короткое стихотворение о снеге.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_14'),
        'Задание 15': ("""Исходный промпт: Опиши средневековый замок.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Опиши средневековый замок.

B: Напиши короткое описание замка.

C: Опиши мрачный средневековый замок с высокими башнями и глубоким рвом, расположенный на вершине скалистого утеса.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_15'),
        'Задание 16': ("""Исходный промпт: Напиши приключенческий рассказ.

Вопрос: Какой из этих промптов даст более качественный результат?
A: Напиши рассказ о группе исследователей, потерявшихся в джунглях Амазонки и борющихся за выживание.

B: Напиши приключенческий рассказ.

C: Напиши короткий рассказ о путешествии.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_16'),
        'Задание 17': ("""Исходный промпт: Напиши монолог персонажа.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши монолог персонажа.

B: Напиши эмоциональный монолог персонажа, который только что узнал о предательстве близкого друга.

C: Напиши короткий монолог о дружбе.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_17'),
        'Задание 18': ("""Исходный промпт: Опиши городскую площадь.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Опиши городскую площадь.

B: Напиши короткое описание площади.

C: Опиши оживленную городскую площадь вечером, с яркими огнями кафе и спокойно гуляющими людьми.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_18'),
        'Задание 19': ("""Исходный промпт: Напиши рассказ о детях на празднике.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши рассказ о детях на празднике.

B: Напиши рассказ о празднике, где играют дети.

C: Напиши рассказ о детях, радостно играющих на день рождения с воздушными шариками и тортом.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_19'),
        'Задание 20': ("""Исходный промпт: Напиши рассказ о путешествии.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши рассказ о путешествии по Японии, описывая уникальные традиции и культурные особенности, с которыми сталкивается главный герой.

B: Напиши рассказ о путешествии.

C: Напиши короткий рассказ о поездке за границу.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_20'),
        'Задание 21': ("""Исходный промпт: Напиши письмо другу.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши письмо другу, рассказывая о своих успехах в университете и планах на летние каникулы.

B: Напиши письмо другу.

C: Напиши короткое письмо о своей жизни.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_21'),
        'Задание 22': ("""Исходный промпт: Напиши статью о здоровье.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши статью о здоровье.

B: Напиши статью о важности регулярных физических упражнений для поддержания здоровья и хорошего самочувствия.

C: Напиши короткую статью о пользе спорта.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_22'),
        'Задание 23': ("""Исходный промпт: Напиши рассказ о путешествии.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши интересный рассказ о путешествии.

B: Напиши короткий рассказ о путешествии.

C: Напиши рассказ от первого лица о пешем путешествии по Гималаям, полном неожиданных встреч с местными жителями и трудностей, которые закаляют характер.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_23'),
        'Задание 24': ("""Исходный промпт: Напиши рассказ о приключениях.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши рассказ о приключениях группы друзей, которые исследуют заброшенный замок в лесу.
B: Напиши рассказ о приключениях.
C: Напиши короткий рассказ о приключениях.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_24'),
        'Задание 25': ("""Исходный промпт: Напиши статью о технологиях.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши статью о технологиях.

B: Напиши короткую статью о технологиях.

C: Напиши статью о влиянии искусственного интеллекта на будущее работы.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_25'),
        'Задание 26': ("""Исходный промпт: Напиши стихотворение о природе.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши стихотворение о природе.

B: Напиши стихотворение о весеннем лесу, полном цветущих деревьев и поющих птиц.

C: Напиши короткое стихотворение о лесе.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_26'),
        'Задание 27': ("""Исходный промпт: Напиши письмо родителям.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши письмо родителям.

B: Напиши короткое письмо о своей жизни.

C:Напиши письмо родителям, в котором расскажешь о своих успехах в университете и планах на лето.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_27'),
        'Задание 28': ("""Исходный промпт: Напиши рассказ о дружбе.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши рассказ о дружбе.

B: Напиши короткий рассказ о друзьях.

C: Напиши рассказ о двух друзьях, преодолевающих вместе жизненные преграды и становящихся сильнее благодаря своей дружбе.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_28'),
        'Задание 29': ("""Исходный промпт: Напиши инструкцию по уходу за растением.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши инструкцию по уходу за растением.
                 
B: Напиши подробную инструкцию по уходу за фиалкой в домашних условиях, включая информацию о поливе, освещении и удобрении.

C: Напиши короткую инструкцию о том, как ухаживать за цветком.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_29'),
        'Задание 30': ("""Исходный промпт: Напиши эссе о спорте.

Вопрос: Какой из этих промптов даст более качественный результат?

A: Напиши эссе о влиянии регулярных занятий спортом на физическое и психическое здоровье молодежи.

B: Напиши эссе о спорте.

C: Напиши короткое эссе о пользе физических упражнений.

Пожалуйста, выберите ваш ответ:""", 'waiting_answer_30'),
    }
    
    if message.text.startswith('Задание '):
        task_number = message.text.split()[1]
        task_key = f'Задание {task_number}'
        if task_key in tasks:
            user_states[message.from_user.id] = tasks[task_key][1]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(*[types.KeyboardButton(btn) for btn in 'ABC'])
            bot.send_message(message.chat.id, tasks[task_key][0], reply_markup=markup)
    elif message.text == 'Вернуться в главное меню':
        return_to_main_menu(message)
    elif message.text in ['A', 'B', 'C']:
        check_answer(message)
    else:
        bot.send_message(message.chat.id, 'Пожалуйста, выберите задание, ответьте на вопрос или вернитесь в главное меню')

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, 'main_menu')
    if state == 'main_menu':
        handle_main_menu(message)
    elif state == 'tasks':
        handle_tasks(message)
    elif state.startswith('waiting_answer_'):
        if message.text in ['A', 'B', 'C']:
            check_answer(message)
        else:
            bot.send_message(message.chat.id, 'Пожалуйста, ответьте A, B или C.')
    else:
        bot.send_message(message.chat.id, 'Извините, я не понимаю. Пожалуйста, используйте кнопки меню.')

def check_answer(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    correct_answers = {
        'waiting_answer_1': 'A',
        'waiting_answer_2': 'C',
        'waiting_answer_3': 'B',
        'waiting_answer_4': 'C',
        'waiting_answer_5': 'B',
        'waiting_answer_6': 'B',
        'waiting_answer_7': 'A',
        'waiting_answer_8': 'A',
        'waiting_answer_9': 'B',
        'waiting_answer_10': 'A',
        'waiting_answer_11': 'C',
        'waiting_answer_12': 'B',
        'waiting_answer_13': 'B',
        'waiting_answer_14': 'A',
        'waiting_answer_15': 'C',
        'waiting_answer_16': 'A',
        'waiting_answer_17': 'B',
        'waiting_answer_18': 'C',
        'waiting_answer_19': 'C',
        'waiting_answer_20': 'A',
        'waiting_answer_21': 'A',
        'waiting_answer_22': 'B',
        'waiting_answer_23': 'C',
        'waiting_answer_24': 'A',
        'waiting_answer_25': 'C',
        'waiting_answer_26': 'B',
        'waiting_answer_27': 'C',
        'waiting_answer_28': 'C',
        'waiting_answer_29': 'B',
        'waiting_answer_30': 'A'
    }

    explanations = {
        'waiting_answer_1': 'Промпт A предоставляет больше конкретики: стиль (хайку), цвет кошки (черная), и местоположение (подоконник). Это помогает LLM создать более детализированное и интересное стихотворение.',
        'waiting_answer_2': 'Промпт C указывает на конкретную целевую аудиторию (подростки), платформу (Instagram), конкретные полезные свойства (акне и энергия), и даже стиль (указание на хэштеги). Это поможет LLM сгенерировать более привлекательный и релевантный контент.',
        'waiting_answer_3': 'Промпт B дает четкое направление, описывая проблему, которую должно решать приложение (улучшение сна), и предлагая конкретные функции. Это ограничивает поле поиска для LLM и направляет его на создание более практичной и полезной идеи.',
        'waiting_answer_4': 'Промпт C определяет целевую аудиторию (пятилетний ребенок) и задает требования к стилю объяснения (простые примеры, избегание сложной терминологии). Это позволяет LLM адаптировать объяснение под конкретного слушателя.',
        'waiting_answer_5': 'Промпт B предоставляет конкретные детали (неисправный товар, номер заказа) и четкие инструкции (вежливость, профессионализм, подробное описание проблемы, запрос на возврат денег). Это помогает LLM создать более эффективное и целенаправленное письмо.',
        'waiting_answer_6': 'Промпт B уточняет тему (изменение климата и тропические леса), что позволяет LLM создать более глубокое и содержательное эссе.',
        'waiting_answer_7': 'Промпт A предоставляет конкретные детали (первая любовь, нежность, воспоминания), что позволяет LLM создать более эмоциональное и трогательное стихотворение.',
        'waiting_answer_8': 'Промпт C уточняет сюжет (преодоление трудностей, поддержка), что позволяет LLM создать более глубокий и значимый рассказ.',
        'waiting_answer_9': 'Промпт B указывает конкретное блюдо (паста с соусом песто и курицей), что позволяет LLM создать более детальную и полезную инструкцию.',
        'waiting_answer_10': 'Промпт A уточняет детали праздника (день рождения, воздушные шарики, торт), создавая яркое и живое описание.',
        'waiting_answer_11': 'Промпт C предоставляет больше деталей: описание цвета (золотые листья), атмосферы (свежий и прохладный воздух), что помогает LLM создать более яркую картину.',
        'waiting_answer_12': 'Промпт B уточняет контекст (летний день) и игру (прятки), что помогает LLM создать более живописное и атмосферное описание.',
        'waiting_answer_13': 'Промпт B предоставляет конкретный фокус (влияние на чувства и восприятие), что помогает создать более глубокое и проработанное эссе.',
        'waiting_answer_14': 'Промпт A уточняет атмосферу (мороз, снежное падение), что позволяет создать более детализированное и образное стихотворение.',
        'waiting_answer_15': 'Промпт C дает дополнительные детали, такие как мрачные башни и заросшие скалы, что создаёт атмосферу и визуализирует замок более ярко.',
        'waiting_answer_16': 'Промпт A уточняет место (Амазонка) и ситуацию (потерявшиеся исследователи, борьба за выживание), что создаёт более напряжённый и детализированный сюжет.',
        'waiting_answer_17': 'Промпт B дает более конкретное описание ситуации, что позволяет создать более эмоционально насыщенный и личный монолог.',
        'waiting_answer_18': 'Промпт C включает детали, такие как яркие огни и спокойные гуляющие люди, создавая атмосферу и визуальные образы.',
        'waiting_answer_19': 'Промпт C уточняет детали праздника (день рождения, воздушные шарики, торт), создавая яркое и живое описание.',
        'waiting_answer_20': 'Промпт A содержит конкретные детали (Япония, традиции, культура), что позволяет LLM создать более увлекательный и насыщенный рассказ.',
        'waiting_answer_21': 'Промпт A содержит конкретные детали (успехи в университете, планы на лето), что позволяет LLM создать более личное и интересное письмо.',
        'waiting_answer_22': 'Промпт B уточняет тему (спорт и стресс), что позволяет LLM создать более целенаправленную и информативную статью.',
        'waiting_answer_23': 'Промпт C дает конкретную перспективу (от первого лица), место (Гималаи), акцент (встречи и трудности) и ожидаемый эффект (закалка характера). Это помогает LLM создать более богатый и вовлекающий рассказ.',
        'waiting_answer_24': 'Промпт A содержит конкретные детали (группа друзей, заброшенный замок, лес), что позволяет LLM создать более увлекательный и насыщенный рассказ.',
        'waiting_answer_25': 'Промпт C уточняет тему (искусственный интеллект и работа), что позволяет LLM создать более целенаправленную и информативную статью.',
        'waiting_answer_26': 'Промпт B предоставляет конкретные детали (весенний лес, цветущие деревья, птицы), что позволяет LLM создать более живописное и яркое стихотворение.',
        'waiting_answer_27': 'Промпт C содержит конкретные детали (успехи в учебе, выпускной), что позволяет LLM создать более личное и интересное письмо.',
        'waiting_answer_28': 'Промпт C уточняет сюжет (преодоление преград), что позволяет LLM создать более глубокий и трогательный рассказ.',
        'waiting_answer_29': 'Промпт B предоставляет конкретные детали (фиалка, домашние условия), что позволяет LLM создать более полезную и точную инструкцию.',
        'waiting_answer_30': 'Промпт A уточняет тему (влияние спорта на здоровье молодежи), что позволяет LLM создать более содержательное и целенаправленное эссе.'
    
    }

    if state in correct_answers:
        is_correct = message.text == correct_answers[state]
        response = 'Правильно! ' if is_correct else f'К сожалению, это неправильный ответ. Правильный ответ - {correct_answers[state]}. '
        response += explanations.get(state, '')
        bot.send_message(message.chat.id, response)
        user_answers[user_id] = is_correct
    
    return_to_tasks_menu(message)
    

def return_to_tasks_menu(message):
    user_states[message.from_user.id] = 'tasks'
    markup = generate_tasks_keyboard()
    bot.send_message(message.chat.id, 'Выберите следующее задание или вернитесь в главное меню:', reply_markup=markup)


def return_to_main_menu(message):
    user_states[message.from_user.id] = 'main_menu'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Ознакомление с курсом')
    btn2 = types.KeyboardButton('Задания')
    btn3 = types.KeyboardButton('Тренировка')
    btn4 = types.KeyboardButton('Оценка промпта')
    web_app = types.WebAppInfo(url="https://lunarcelestia.github.io/GPTuchit_store/") 
    btn_web_app = types.KeyboardButton(text="Курсы", web_app=web_app)
    
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    markup.row(btn_web_app) 
    
    bot.send_message(message.chat.id, 'Вы вернулись в главное меню', reply_markup=markup)

app = Flask(__name__)

# вебхук 
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# эндпоинт для render
@app.route("/", methods=["GET"])
def index():
    return "Бот работает!", 200

# эндпоинт для самопинга
@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

def keep_alive():
    try:
        app_url = "https://gptuchit.onrender.com"
        requests.get(f"{app_url}/ping", timeout=10)
        print(f"[{datetime.now().isoformat()}] Ping successful")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Ping failed: {e}")
    
    threading.Timer(1500, keep_alive).start()

#запуск фласка
if __name__ == "__main__":
    webhook_url = f"https://gptuchit.onrender.com/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)


    keep_alive()


    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

