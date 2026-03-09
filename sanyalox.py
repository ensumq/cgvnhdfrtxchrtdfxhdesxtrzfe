import asyncio
import logging
import random
from collections import deque
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ВСТАВЬ СЮДА СВОЙ ТОКЕН ОТ BOTFATHER
BOT_TOKEN = "sanyalox228"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

games = {}
global_game_counter = 0

# --- ИГРОВЫЕ КЛАССЫ ---

class Player:
    def __init__(self, user_id: int, name: str, number: int):
        self.user_id = user_id
        self.name = name
        self.number = number 
        self.role = None
        self.is_alive = True
        self.is_glued = False 
        self.has_alibi = False
        
        # Переменные для ночных способностей
        self.surikens = 0
        self.last_healed = None 
        self.last_alibi = None 
        self.last_man_heal = False 
        self.found_mafia = False 
        self.found_mafia_day = -1
        self.last_rek = None 

class Game:
    def __init__(self, chat_id: int):
        global global_game_counter
        self.chat_id = chat_id
        self.players = {} 
        self.players_by_number = {} 
        self.state = "LOBBY" 
        
        global_game_counter += 1
        self.game_number = global_game_counter
        self.day_count = 0
        self.day_starter_num = 1

        self.nominated = [] 
        self.speech_queue = deque()
        self.current_speech_task = None
        
        self.voting_queue = deque() 
        self.current_votes = {} 
        self.balance_players = [] 
        self.revote_count = 0 
        
        
        self.night_actions = {} 
        self.expected_night_actors = {} 
        self.mafia_team = ["Мафия", "Дон", "Адвокат", "Ниндзя"]
        self.current_preset = []

    def add_player(self, user_id: int, name: str):
        if user_id not in self.players:
            number = len(self.players) + 1
            player = Player(user_id, name, number)
            self.players[user_id] = player
            self.players_by_number[number] = player
            return True
        return False

    def get_alive_players(self):
        return [p for p in self.players.values() if p.is_alive]

    def build_daily_queue(self):
        alive = sorted(self.get_alive_players(), key=lambda p: p.number)
        if not alive: return deque()
        
        start_idx = 0
        for i, p in enumerate(alive):
            if p.number >= self.day_starter_num:
                start_idx = i
                break
                
        self.day_starter_num = alive[start_idx].number
        queue = deque(alive)
        queue.rotate(-start_idx)
        return queue

# --- ПРЕСЕТЫ РОЛЕЙ ---
ROOM_PRESETS = {
    4: [ 
        ["Маньяк с бинтами", "Адвокат", "Двуликий", "Шериф"]
    ],
    5: [ 
        ["Мафия", "Шериф", "Доктор", "Мирный житель", "Вор"]
    ],
    6: [
        ["Дон", "Мафия", "Шериф", "Доктор", "Мирный житель", "Мирный житель"],
        ["Дон", "Мафия", "Шериф", "Тула", "Мирный житель", "Мирный житель"],
        ["Маньяк с бинтами", "Мафия", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"]
    ],
    7: [
        ["Двуликий", "Дон", "Шериф", "Доктор", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Двуликий", "Дон", "Шериф", "Тула", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Ниндзя", "Мафия", "Тула", "Шериф", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Мафия", "Маньяк с бинтами", "Вор", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Бессмертный", "Шериф", "Мафия", "Ниндзя", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Мафия", "Маньяк с бинтами", "Шериф", "Бессмертный", "Мирный житель", "Мирный житель"]
    ],
    8: [
        ["Адвокат", "Ниндзя", "Маньяк с бинтами", "Бессмертный", "Доктор", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Ниндзя", "Маньяк с бинтами", "Бессмертный", "Тула", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Двуликий", "Ниндзя", "Маньяк с бинтами", "Бессмертный", "Доктор", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Вор", "Доктор", "Дон", "Ниндзя", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Бессмертный", "Вор", "Ниндзя", "Адвокат", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Дон", "Ниндзя", "Шериф", "Бессмертный", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Маньяк с бинтами", "Мафия", "Мафия", "Шериф", "Доктор", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Дон", "Мафия", "Шериф", "Тула", "Бессмертный", "Маньяк с бинтами", "Мирный житель", "Мирный житель"]
    ],
    9: [
        ["Мафия", "Мафия", "Мафия", "Маньяк с бинтами", "Шериф", "Бессмертный", "Доктор", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Маньяк с бинтами", "Шериф", "Бессмертный", "Тула", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Двуликий", "Ниндзя", "Маньяк с бинтами", "Доктор", "Бессмертный", "Шериф", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Двуликий", "Ниндзя", "Маньяк с бинтами", "Тула", "Бессмертный", "Шериф", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Бессмертный", "Вор", "Маньяк с бинтами", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Доктор", "Вор", "Шериф", "Маньяк без бинтов", "Мирный житель", "Мирный житель"]
    ],
    10: [
        ["Мафия", "Мафия", "Мафия", "Маньяк с бинтами", "Шериф", "Бессмертный", "Доктор", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Маньяк с бинтами", "Шериф", "Бессмертный", "Тула", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Двуликий", "Ниндзя", "Маньяк с бинтами", "Доктор", "Бессмертный", "Шериф", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Адвокат", "Двуликий", "Ниндзя", "Маньяк с бинтами", "Тула", "Бессмертный", "Шериф", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Бессмертный", "Вор", "Маньяк с бинтами", "Мирный житель", "Мирный житель", "Мирный житель", "Мирный житель"],
        ["Мафия", "Мафия", "Мафия", "Доктор", "Вор", "Шериф", "Маньяк без бинтов", "Мирный житель", "Мирный житель", "Мирный житель"]
    ]
    
}

# --- ОПИСАНИЯ РОЛЕЙ (ШПАРГАЛКА) ---
ROLE_DESCRIPTIONS = {
    "Мирный житель": "Не имеет ночных способностей. Днем ищет мафию и голосует на суде.",
    "Мафия": "Ночью вместе с командой выбирает жертву для выстрела.",
    "Дон": "Глава мафии. Его голос при стрельбе равен двум. Каждую ночь проверяет одного игрока, ища Шерифа.",
    "Адвокат": "Играет за мафию. Ночью дает одному игроку алиби (спасает от дневной казни на следующий день). Не может дать алиби одному и тому же жителю две ночи подряд",
    "Ниндзя": "Играет за мафию. Ночью кидает сюрикен. Накопление двух сюрикенов убивает цель. (Лечение снимает сюрикены).",
    "Вор": "Просыпается первым. Заклеивает рот: цель лишается дневной речи и ночного хода. Если заклеит мафию — отменяет выстрел всей команды. Не может заклеить одного и того же жителя две ночи подряд",
    "Доктор": "Ночью спасает одного игрока от убийства. Нельзя лечить одного и того же два раза подряд.",
    "Тула": "Ночью лечит игрока и дает ему алиби на день. Если Тулу убьют, ее клиент умирает вместе с ней (кроме Бессмертного). Не может ходить к одному и тому же жителю два ночи подряд",
    "Шериф": "Ночью проверяет игрока, узнавая мафия он или нет (Маньяки  видится мирным всегда, двуликий начинает видеться как мафия со следующей ночи от той, когда он нашел мафию.",
    "Маньяк без бинтов": "Играет сам за себя. Каждую ночь убивает одного игрока. Побеждает, оставшись 1 на 1.",
    "Маньяк с бинтами": "Играет сам за себя. Каждую ночь выбирает: убить игрока ИЛИ вылечить самого себя (нельзя лечить себя 2 ночи подряд).",
    "Двуликий": "Ночью ищет мафию (проверка). Как только найдет — узнает их состав и со следующей ночи убивает сам.",
    "Бессмертный": "Неуязвим ночью: не умирает от выстрелов и сюрикенов. Может уйти только на дневном голосовании."
}

# --- УСЛОВИЯ ПОБЕДЫ ---
async def check_victory(game: Game, chat_id: int) -> bool:
    alive = game.get_alive_players()
    if not alive:
        await bot.send_message(chat_id, "💀 Все игроки погибли! Санек сосет яйца - мафия победила.")
        game.state = "FINISHED"
        return True

    mafia_count = sum(1 for p in alive if p.role in game.mafia_team or (p.role == "Двуликий" and p.found_mafia))
    maniac_count = sum(1 for p in alive if p.role in ["Маньяк без бинтов", "Маньяк с бинтами"])
    town_count = len(alive) - mafia_count - maniac_count

    if maniac_count > 0 and len(alive) == 2:
        await bot.send_message(chat_id, "🔪 Маньяк остался один на один с жертвой! ПОБЕДА МАНЬЯКА!")
        game.state = "FINISHED"
        return True

    if mafia_count == 0 and maniac_count == 0:
        await bot.send_message(chat_id, "🕊 Вся мафия и маньяки уничтожены! ПОБЕДА МИРНОГО ГОРОДА!")
        game.state = "FINISHED"
        return True

    if mafia_count >= (town_count + maniac_count) and maniac_count == 0:
        await bot.send_message(chat_id, "🕴 Мафий за столом стало не меньше, чем мирных! ПОБЕДА МАФИИ!")
        game.state = "FINISHED"
        return True

    return False


# --- ОБРАБОТЧИКИ БАЗОВЫХ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type == "private":
        await message.answer("Привет! Я бот для Мафии 🕵️‍♂️\nЯ запомнил тебя. Теперь добавь меня в группу с друзьями и напиши там /start_game.")

@dp.message(Command("start_game"))
async def cmd_start_game(message: types.Message):
    chat_id = message.chat.id
    if message.chat.type == "private": return await message.answer("Играть нужно в группе!")
    if chat_id in games and games[chat_id].state not in ["FINISHED"]: return await message.answer("Игра в этом чате уже запущена!")

    games[chat_id] = Game(chat_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✋ Присоединиться", callback_data="join_game")]])
    await message.answer("Регистрация на Мафию открыта! Нажмите кнопку ниже.", reply_markup=kb)

@dp.callback_query(F.data == "join_game")
async def join_game_handler(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    game = games.get(chat_id)
    if not game or game.state != "LOBBY": return await callback.answer("Нет открытого лобби.", show_alert=True)
        
    user = callback.from_user
    if game.add_player(user.id, user.first_name):
        text = f"Зарегистрировано: {len(game.players)} чел.\n" + "\n".join([f"{p.number}. {p.name}" for p in game.players.values()])
        await callback.message.edit_text(text, reply_markup=callback.message.reply_markup)
        await callback.answer("Ты в игре!")
    else:
        await callback.answer("Ты уже зарегистрирован!", show_alert=True)

@dp.message(Command("run"))
async def cmd_run(message: types.Message):
    chat_id = message.chat.id
    game = games.get(chat_id)
    if not game or game.state != "LOBBY": return
        
    player_count = len(game.players)
    if player_count not in ROOM_PRESETS: return await message.answer(f"Для старта нужно другое количество игроков (сейчас {player_count}).")
        
    roles = random.choice(ROOM_PRESETS[player_count]).copy()
    game.current_preset = roles.copy() 
    random.shuffle(roles)
    
    game.day_starter_num = ((game.game_number - 1) % player_count) + 1
    
    # 1. Сначала просто назначаем роли всем игрокам
    for i, player in enumerate(game.players.values()):
        player.role = roles[i]
        
    # 2. Формируем текст со списком всей команды мафии
    mafia_members = [p for p in game.players.values() if p.role in game.mafia_team]
    mafia_text = "\n".join([f"№{p.number} — {p.name} ({p.role})" for p in mafia_members])
    
    # 3. Рассылаем роли
    for player in game.players.values():
        msg = f"Твоя роль: {player.role}"
        
        # Если игрок — мафия, приклеиваем список союзников
        if player.role in game.mafia_team:
            msg += f"\n\n🕴 Твоя команда:\n{mafia_text}\n\n*Ночью вы можете общаться с командой прямо здесь, отправляя сообщения боту!*"
            
        try:
            await bot.send_message(player.user_id, msg)
        except:
            return await message.answer(f"Не удалось отправить роль игроку {player.name}. Он не нажал /start в личке с ботом!")
            
    game.state = "DAY"
    game.day_count = 1
    
    await message.answer(f"🎲 Игра началась!\nПресет ролей: {', '.join(game.current_preset)}")
    
    unique_roles = set(game.current_preset)
    desc_text = "📖 <b>Справка по ролям на эту игру:</b>\n\n"
    for r in unique_roles:
        desc = ROLE_DESCRIPTIONS.get(r, "Описание отсутствует.")
        desc_text += f"🔹 <b>{r}</b>: {desc}\n\n"
        
    await message.answer(desc_text, parse_mode="HTML")
    await start_day_phase(game, chat_id)

@dp.message(Command("alive"))
async def cmd_alive(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state in ["LOBBY", "FINISHED"]: 
        return await message.answer("Игра сейчас не идет.")
        
    # Сортируем игроков по номерам для красоты
    alive = sorted(game.get_alive_players(), key=lambda p: p.number)
    text = "👤 Живые игроки за столом:\n" + "\n".join([f"№{p.number} — {p.name}" for p in alive])
    await message.answer(text)


# --- ЧАТ МАФИИ (Писать в ЛС боту ночью) ---
@dp.message(F.chat.type == "private")
async def mafia_night_chat(message: types.Message):
    # Игнорируем команды (начинаются со слеша)
    if message.text and message.text.startswith("/"): return
    
    user_id = message.from_user.id
    
    # Ищем, в какой игре сейчас участвует пользователь
    active_game = None
    player = None
    for game in games.values():
        if user_id in game.players and game.state in ["NIGHT_THIEF", "NIGHT"]:
            active_game = game
            player = game.players[user_id]
            break
            
    if not active_game or not player or not player.is_alive: return
    if player.role not in active_game.mafia_team: return
    
    # Если мафию заклеил Вор, она не может общаться
    if player.is_glued:
        return await message.answer("🤐 Вы заклеены Вором! Вы не можете говорить в чате мафии этой ночью.")
        
    if not message.text:
        return await message.answer("⚠️ В чат мафии можно отправлять только текстовые сообщения.")

    # Рассылаем сообщение остальным живым мафиози
    sent_count = 0
    for other_p in active_game.get_alive_players():
        if other_p.role in active_game.mafia_team and other_p.user_id != user_id:
            try:
                await bot.send_message(
                    other_p.user_id, 
                    f"🥷 [Чат мафии] Игрок №{player.number}: {message.text}"
                )
                sent_count += 1
            except: pass
            
    # Если остальные убиты, предупреждаем игрока
    if sent_count == 0:
        await message.answer("🥷 Вы остались единственным живым мафиози. Вас некому читать.")

@dp.message(Command("roles"))
async def cmd_roles(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state == "LOBBY": return
    await message.answer(f"📜 Набор ролей в этой игре:\n{', '.join(game.current_preset)}")
# --- ФАЗА ДНЯ: РЕЧИ И ВЫСТАВЛЕНИЯ ---

async def start_day_phase(game: Game, chat_id: int):
    # Если это не первый день игры, передаем право первого слова следующему
    if game.day_count > 1:
        alive_nums = sorted([p.number for p in game.get_alive_players()])
        if alive_nums:
            next_starter = alive_nums[0] # На случай если дошли до конца круга
            for num in alive_nums:
                if num > game.day_starter_num:
                    next_starter = num
                    break
            game.day_starter_num = next_starter

    game.nominated = []
    game.speech_queue = game.build_daily_queue()
    if not game.speech_queue: return
        
    first_player = game.speech_queue[0]
    await bot.send_message(chat_id, f"☀️ Наступает День {game.day_count}.\nПервым говорит Игрок №{first_player.number}. Напишите /speech.")

async def next_speaker(game: Game, chat_id: int):
    if game.speech_queue: game.speech_queue.popleft() 
    while game.speech_queue and game.speech_queue[0].is_glued:
        glued_p = game.speech_queue.popleft()
        await bot.send_message(chat_id, f"🤐 Игрок №{glued_p.number} заклеен Вором и пропускает свою речь.")

    if game.speech_queue:
        next_p = game.speech_queue[0]
        await bot.send_message(chat_id, f"🗣 Очередь Игрока №{next_p.number}. Напишите /speech для начала речи.")
    else:
        await bot.send_message(chat_id, "🎙 Все речи окончены! Переходим к голосованию. Напишите /start_vote.")

@dp.message(Command("speech"))
async def cmd_speech(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state != "DAY" or not game.speech_queue: return
    player = game.players.get(message.from_user.id)
    if not player or player.user_id != game.speech_queue[0].user_id: return await message.answer("Сейчас не ваша очередь говорить!")
    if game.current_speech_task and not game.current_speech_task.done(): return await message.answer("Вы уже выступаете!")

    await message.answer(f"⏱ Игрок №{player.number}, ваша минута пошла!\n"
                         f"Вы можете выставлять кандидатов: /nominate <номер>\n"
                         f"Чтобы закончить речь досрочно: /end_speech")

    async def timer_task():
        try:
            await asyncio.sleep(60)
            if player.is_alive and game.state == "DAY":
                await bot.send_message(message.chat.id, f"🛑 Игрок №{player.number}, время вышло!")
                await next_speaker(game, message.chat.id)
        except asyncio.CancelledError: pass
        finally: game.current_speech_task = None

    game.current_speech_task = asyncio.create_task(timer_task())

@dp.message(Command("end_speech"))
async def cmd_end_speech(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state != "DAY" or not game.speech_queue: return
    player = game.players.get(message.from_user.id)
    if not player or player.user_id != game.speech_queue[0].user_id: return
    if game.current_speech_task and not game.current_speech_task.done(): game.current_speech_task.cancel()
    await message.answer(f"✅ Игрок №{player.number} завершил свою речь.")
    await next_speaker(game, message.chat.id)

@dp.message(Command("nominate"))
async def cmd_nominate(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state != "DAY" or not game.speech_queue: return
    player = game.players.get(message.from_user.id)
    if not player or player.user_id != game.speech_queue[0].user_id: return await message.answer("Только во время своей речи!")

    try: target_num = int(message.text.split()[1])
    except: return await message.answer("Формат: /nominate <номер>")

    if target_num not in game.players_by_number or not game.players_by_number[target_num].is_alive: return await message.answer("Этого игрока нет за столом.")
    if target_num not in game.nominated:
        game.nominated.append(target_num)
        await message.answer(f"👉 Игрок №{target_num} выставлен на голосование.")

@dp.message(Command("nominated"))
async def cmd_nominated(message: types.Message):
    game = games.get(message.chat.id)
    if game and game.nominated: await message.answer("Выставлены: " + ", ".join(map(str, game.nominated)))
    else: await message.answer("Пока никто не выставлен.")


# --- ФАЗА ГОЛОСОВАНИЯ И БАЛАНСА ---

@dp.message(Command("start_vote"))
async def cmd_start_vote(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state != "DAY": return
    if game.current_speech_task and not game.current_speech_task.done(): game.current_speech_task.cancel()

    if not game.nominated:
        await message.answer("Никто не выставлен. Город засыпает...")
        await start_night_phase(game, message.chat.id)
        return

    game.state = "VOTING"
    game.current_votes = {num: 0 for num in game.nominated}
    game.voting_queue = game.build_daily_queue() 
    await message.answer(f"🗳 Начинаем голосование! Выставлены: {game.nominated}.\nПервым голосует Игрок №{game.voting_queue[0].number}. Пишите /vote <номер>")

@dp.message(Command("vote"))
async def cmd_vote(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state not in ["VOTING", "REVOTE"]: return
    player = game.players.get(message.from_user.id)
    if not player or not game.voting_queue or player.user_id != game.voting_queue[0].user_id: return await message.answer("Сейчас не ваша очередь голосовать!")

    try: target_num = int(message.text.split()[1])
    except: return await message.answer("Формат: /vote <номер>")

    allowed = game.balance_players if game.state == "REVOTE" else game.nominated
    if target_num not in allowed: return await message.answer(f"Голосовать можно только за: {allowed}")

    game.current_votes[target_num] += 1
    game.voting_queue.popleft()
    await message.answer(f"🗣 Игрок №{player.number} проголосовал против Игрока №{target_num}!")

    if not game.voting_queue: await calculate_votes(game, message.chat.id)
    else: await message.answer(f"Следующий голосует Игрок №{game.voting_queue[0].number}.")

async def calculate_votes(game: Game, chat_id: int):
    max_votes = max(game.current_votes.values())
    leaders = [num for num, votes in game.current_votes.items() if votes == max_votes]

    if len(leaders) == 1:
        killed_num = leaders[0]
        if game.players_by_number[killed_num].has_alibi:
            await bot.send_message(chat_id, f"🛡 Игрок №{killed_num} должен был покинуть стол, но у него оказалось АЛИБИ! Он выживает.")
        else:
            game.players_by_number[killed_num].is_alive = False
            await bot.send_message(chat_id, f"💀 Игрок №{killed_num} покидает стол!")
            
        if await check_victory(game, chat_id): return
        
        await bot.send_message(chat_id, "Город засыпает...")
        await start_night_phase(game, chat_id)
    else:
        if game.revote_count >= 1:
            await bot.send_message(chat_id, "⚖️ Голоса снова разделились! Автоматическое оправдание. Город засыпает...")
            await start_night_phase(game, chat_id)
            return
            
        game.balance_players = leaders
        game.state = "BALANCE"
        game.current_votes = {"acquit": 0, "kill": 0, "revote": 0}
        game.voting_queue = game.build_daily_queue()
        await bot.send_message(chat_id, f"⚖️ Баланс между: {leaders}.\n1 (Оправдать), 2 (Убить всех), 3 (Переголосовать).\nПишите /balance <1/2/3>. Первым голосует Игрок №{game.voting_queue[0].number}.")

@dp.message(Command("balance"))
async def cmd_balance_vote(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state != "BALANCE": return
    player = game.players.get(message.from_user.id)
    if not player or not game.voting_queue or player.user_id != game.voting_queue[0].user_id: return

    try: choice = int(message.text.split()[1])
    except: return
    if choice not in [1, 2, 3]: return

    options = {1: "acquit", 2: "kill", 3: "revote"}
    names = {1: "Оправдать", 2: "Убить", 3: "Переголосовать"}
    
    game.current_votes[options[choice]] += 1
    game.voting_queue.popleft()
    await message.answer(f"🗣 Игрок №{player.number} выбрал: {names[choice]}!")

    if not game.voting_queue: await resolve_balance(game, message.chat.id)
    else: await message.answer(f"Следующий голосует Игрок №{game.voting_queue[0].number}.")

async def resolve_balance(game: Game, chat_id: int):
    v = game.current_votes
    max_v = max(v.values())
    
    if v["revote"] == max_v:
        game.revote_count += 1
        game.state = "REVOTE"
        game.current_votes = {num: 0 for num in game.balance_players}
        game.voting_queue = game.build_daily_queue()
        await bot.send_message(chat_id, "🔄 ПЕРЕГОЛОСОВАНИЕ! Пишите /vote <номер> за игроков на балансе.")
    elif v["acquit"] == max_v:
        await bot.send_message(chat_id, "🕊 Все ОПРАВДАНЫ.")
        await start_night_phase(game, chat_id)
    else:
        killed = []
        saved = []
        for num in game.balance_players: 
            if game.players_by_number[num].has_alibi: saved.append(num)
            else:
                game.players_by_number[num].is_alive = False
                killed.append(num)
        
        msg = f"💀 По результатам баланса убиты: {killed if killed else 'никто'}."
        if saved: msg += f"\n🛡 Спасены алиби: {saved}."
        await bot.send_message(chat_id, msg)
        
        if await check_victory(game, chat_id): return
        
        await bot.send_message(chat_id, "Город засыпает...")
        await start_night_phase(game, chat_id)


# --- ФАЗА НОЧИ ДЛЯ ВСЕХ РОЛЕЙ ---

@dp.message(Command("start_night"))
async def cmd_start_night(message: types.Message):
    game = games.get(message.chat.id)
    if not game or game.state in ["LOBBY", "NIGHT", "FINISHED"]: return
    if game.current_speech_task and not game.current_speech_task.done(): game.current_speech_task.cancel()
    await message.answer("🌙 Принудительно наступает Ночь! Город засыпает...")
    await start_night_phase(game, message.chat.id)

async def start_night_phase(game: Game, chat_id: int):
    game.state = "NIGHT_THIEF"
    game.night_actions = {} 
    game.expected_night_actors = {} 
    
    for p in game.players.values():
        p.is_glued = False
        p.has_alibi = False

    alive_players = game.get_alive_players()
    game.mafia_team = ["Мафия", "Дон", "Адвокат", "Ниндзя"]
    
    thief = next((p for p in alive_players if p.role == "Вор"), None)
    thief_in_preset = "Вор" in game.current_preset

    if thief:
        # СНАЧАЛА ПИШЕМ В ГРУППУ, ЧТО ЖДЕМ ВОРА (как и при мертвом)
        await bot.send_message(chat_id, "🌙 Ждем ход Вора...")
        
        # Затем отправляем ему кнопки в личку
        game.expected_night_actors[thief.user_id] = ["rek"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"№{t.number} ({t.name})", callback_data=f"n|{chat_id}|rek|{t.number}")] 
            for t in alive_players
        ] + [[InlineKeyboardButton(text="Никого не клеить", callback_data=f"n|{chat_id}|rek|0")]])
        
        try: 
            await bot.send_message(thief.user_id, "Кого будем клеить?", reply_markup=kb)
        except Exception as e: 
            print(f"Ошибка отправки Вору: {e}")
            await bot.send_message(chat_id, "🤐 Вор не смог сделать ход (нет связи).")
            await start_night_others(game, chat_id)

    elif thief_in_preset:
        # Если вор мертв, но был в пресете - имитируем его раздумья
        await bot.send_message(chat_id, "🌙 Ждем ход Вора...")
        await asyncio.sleep(random.randint(20, 45))
        await bot.send_message(chat_id, "🤐 Вор никого не заклеил.")
        await start_night_others(game, chat_id)
    else:
        # Если вора не было в пресете - сразу переходим к остальным
        await start_night_others(game, chat_id)

async def start_night_others(game: Game, chat_id: int):
    game.state = "NIGHT"
    game.expected_night_actors.clear()
    alive_players = game.get_alive_players()
    
    for p in alive_players:
        # Вор уже сходил, заклеенные спят
        if p.role == "Вор" or p.is_glued: continue 
        
        actions = []
        if p.role in game.mafia_team: actions.append(("vote", "Кого убиваем?"))
        if p.role == "Доктор": actions.append(("heal", "Кого будем лечить? (нельзя того же, что и вчера)"))
        if p.role == "Тула": actions.append(("tula", "К кому идем? (хил + алиби)"))
        if p.role == "Шериф": actions.append(("check_s", "Кого проверим на мафию?"))
        if p.role == "Дон": actions.append(("check_d", "Кого проверим на Шерифа?"))
        if p.role == "Адвокат": actions.append(("alibi", "Кому даем алиби на день?"))
        if p.role == "Ниндзя": actions.append(("sur", "В кого кидаем сюрикен?"))
        if p.role == "Маньяк без бинтов": actions.append(("man_k", "Кого убиваем?"))
        if p.role == "Маньяк с бинтами": 
            actions.append(("man_k", "Кого убиваем? (ИЛИ выберите лечение себя)"))
            actions.append(("man_h", "Вылечить себя?"))
        if p.role == "Двуликий":
            if getattr(p, 'found_mafia', False): actions.append(("dvul_k", "Кого убиваем?"))
            else: actions.append(("dvul_j", "Ищем мафию (проверка):"))

        if actions:
            game.expected_night_actors[p.user_id] = [act[0] for act in actions]
            game.night_actions.setdefault(p.user_id, {})
            for act_code, text in actions:
                if act_code == "man_h":
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Лечить себя", callback_data=f"n|{chat_id}|{act_code}|{p.number}")]])
                else:
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"№{t.number} ({t.name})", callback_data=f"n|{chat_id}|{act_code}|{t.number}")] for t in alive_players])
                try: await bot.send_message(p.user_id, text, reply_markup=kb)
                except Exception as e: print(f"Ошибка отправки игроку {p.name}: {e}")

    if not game.expected_night_actors:
        await resolve_night(game, chat_id)

@dp.callback_query(F.data.startswith("n|"))
async def handle_night_action(callback: types.CallbackQuery):
    data = callback.data.split("|")
    chat_id, act_code, target_num = int(data[1]), data[2], int(data[3])
    
    game = games.get(chat_id)
    if not game or game.state not in ["NIGHT", "NIGHT_THIEF"]: return await callback.answer("Ночь уже прошла!", show_alert=True)
    
    user_id = callback.from_user.id
    player = game.players.get(user_id)
    
    if not player or user_id not in game.expected_night_actors or act_code not in game.expected_night_actors[user_id]:
        return await callback.answer("Это действие вам сейчас недоступно.", show_alert=True)

    # # --- ОБРАБОТКА ВОРА ---
    if game.state == "NIGHT_THIEF" and act_code == "rek":
        if target_num != 0 and getattr(player, 'last_rek', None) == target_num:
            return await callback.answer("Нельзя клеить одного и того же игрока две ночи подряд!", show_alert=True)

        game.expected_night_actors[user_id].remove("rek")
        if target_num == 0:
            await callback.message.edit_text("✅ Вы решили никого не клеить.")
            await bot.send_message(chat_id, "🤐 Вор никого не заклеил.")
            player.last_rek = 0
        else:
            target = game.players_by_number[target_num]
            target.is_glued = True
            player.last_rek = target_num
            await callback.message.edit_text(f"✅ Вы заклеили Игрока №{target_num}.")
            await bot.send_message(chat_id, f"🤐 Вор заклеил Игрока №{target_num}! Он пропускает день.")
        
        await start_night_others(game, chat_id)
        return
    # ----------------------
        
    if act_code in ["heal", "tula"] and player.last_healed == target_num: return await callback.answer("Нельзя лечить этого игрока две ночи подряд!", show_alert=True)
    if act_code == "alibi" and player.last_alibi == target_num: return await callback.answer("Нельзя давать алиби этому игроку две ночи подряд!", show_alert=True)
    if act_code == "man_h" and getattr(player, 'last_man_heal', False): return await callback.answer("Нельзя лечить себя 2 дня подряд!", show_alert=True)
        
    game.night_actions[user_id][act_code] = target_num

    # МГНОВЕННЫЕ ПРОВЕРКИ
    if act_code == "check_d":
        t_player = game.players_by_number[target_num]
        ans = f"✅ Игрок №{target_num} — ШЕРИФ!" if t_player.role == "Шериф" else f"❌ Игрок №{target_num} — НЕ ШЕРИФ."
        await bot.send_message(user_id, ans)
    elif act_code == "check_s":
        t_player = game.players_by_number[target_num]
        
        # Двуликий видится черным только со СЛЕДУЮЩЕЙ ночи после того, как нашел мафию
        is_bad_dvul = (t_player.role == "Двуликий" and getattr(t_player, 'found_mafia', False) and getattr(t_player, 'found_mafia_day', -1) < game.day_count)
        
        if t_player.role in game.mafia_team or is_bad_dvul: 
            ans = f"✅ Игрок №{target_num} — МАФИЯ ({t_player.role})!"
        else: 
            ans = f"❌ Игрок №{target_num} — НЕ МАФИЯ."
        await bot.send_message(user_id, ans)
    elif act_code == "dvul_j":
        t_player = game.players_by_number[target_num]
        if t_player.role in game.mafia_team:
            player.found_mafia = True
            player.found_mafia_day = game.day_count
            maf_list = ", ".join([f"№{p.number} ({p.role})" for p in game.get_alive_players() if p.role in game.mafia_team])
            await bot.send_message(user_id, f"🎯 Вы нашли Мафию! Состав: {maf_list}. Со следующей ночи вы убиваете сами.")
            for maf in game.get_alive_players():
                if maf.role in game.mafia_team: await bot.send_message(maf.user_id, f"🎭 Двуликий нашел нас! Это Игрок №{player.number}.")
        else:
            await bot.send_message(user_id, f"❌ Игрок №{target_num} не состоит в Мафии.")
    
    if act_code == "man_k" and "man_h" in game.expected_night_actors[user_id]:
        game.expected_night_actors[user_id].remove("man_h")
        player.last_man_heal = False
    elif act_code == "man_h":
        game.expected_night_actors[user_id].remove("man_k")
        player.last_man_heal = True

    game.expected_night_actors[user_id].remove(act_code)
    await callback.message.edit_text(f"✅ Выбор принят: Игрок №{target_num}")
    
    all_done = all(len(acts) == 0 for acts in game.expected_night_actors.values())
    if all_done: await resolve_night(game, chat_id)

@dp.message(Command("skip_night"))
async def cmd_skip_night(message: types.Message):
    game = games.get(message.chat.id)
    if game:
        if game.state == "NIGHT_THIEF":
            await bot.send_message(message.chat.id, "🤐 Вор проспал. Ход пропущен.")
            await start_night_others(game, message.chat.id)
        elif game.state == "NIGHT":
            await resolve_night(game, message.chat.id)

async def resolve_night(game: Game, chat_id: int):
    healed = set()
    mafia_votes = {}
    killed_this_night = set()
    putana_client = None
    
    shurikens_before = {p.number for p in game.get_alive_players() if p.surikens > 0}
    # Мафия заблокирована, если хотя бы один из живых мафиози заклеен Вором
    mafia_blocked = any(p.is_glued for p in game.get_alive_players() if p.role in game.mafia_team)
    
    actions = []
    for uid, acts in game.night_actions.items():
        for code, target in acts.items():
            actions.append({"actor": game.players[uid], "code": code, "target": game.players_by_number[target]})

    # 1. ДОКТОР, ПУТАНА И МАНЬЯК
    for a in actions:
        if a["actor"].is_glued: continue
        if a["code"] == "heal":
            healed.add(a["target"].number)
            a["actor"].last_healed = a["target"].number
            a["target"].surikens = 0 
        elif a["code"] == "tula":
            healed.add(a["target"].number)
            a["target"].has_alibi = True
            a["actor"].last_healed = a["target"].number
            a["target"].surikens = 0
            putana_client = a["target"]
        elif a["code"] == "man_h":
            healed.add(a["target"].number) # Маньяк успешно спасает сам себя от выстрела

    # 2. АДВОКАТ
    for a in actions:
        if a["code"] == "alibi" and not a["actor"].is_glued:
            a["target"].has_alibi = True
            a["actor"].last_alibi = a["target"].number

    # 3. НИНДЗЯ
    shurikened_this_night = [] # Создаем список для утреннего объявления
    
    for a in actions:
        if a["code"] == "sur" and not a["actor"].is_glued:
            # Сюрикен не вешается, если цель полечили
            if a["target"].number not in healed: 
                a["target"].surikens += 1
                shurikened_this_night.append(a["target"].number)
        

    # 4. МАФИЯ
    mafia_victim = None
    if not mafia_blocked:
        for a in actions:
            if a["code"] == "vote" and not a["actor"].is_glued:
                weight = 2 if a["actor"].role == "Дон" else 1
                mafia_votes[a["target"].number] = mafia_votes.get(a["target"].number, 0) + weight
        if mafia_votes:
            max_v = max(mafia_votes.values())
            leaders = [t for t, v in mafia_votes.items() if v == max_v]
            if leaders: mafia_victim = game.players_by_number[random.choice(leaders)]

    # 5. МАНЬЯКИ И ДВУЛИКИЙ 
    solo_victims = []
    for a in actions:
        if a["actor"].is_glued: continue
        if a["code"] in ["man_k", "dvul_k"]: solo_victims.append(a["target"])

    # 6. РАСЧЕТ СМЕРТЕЙ
    if mafia_victim:
        if mafia_victim.number not in healed and mafia_victim.role != "Бессмертный":
            killed_this_night.add(mafia_victim.number)

    for victim in solo_victims:
        if victim.number not in healed and victim.role != "Бессмертный": 
            killed_this_night.add(victim.number)

    for p in game.get_alive_players():
        if p.surikens >= 2 and p.number not in healed: 
            if p.role == "Бессмертный":
                p.surikens = 0 # Сбрасываем счетчик Бессмертному (как при лечении)
            else:
                killed_this_night.add(p.number)

    # Универсальная проверка смерти Тулы (от мафии, маньяка или сюрикенов)
    for p in game.get_alive_players():
        if p.role == "Тула" and p.number in killed_this_night:
            # Если Тула ходила к кому-то, и это не она сама
            if putana_client and putana_client.number != p.number:
                # Бессмертный переживает смерть Тулы
                if putana_client.role != "Бессмертный":
                    killed_this_night.add(putana_client.number)

    
    
    # 7. ИТОГИ НОЧИ
    announcement = "☀️ Город просыпается.\n\n"
    if killed_this_night:
        for num in killed_this_night: game.players_by_number[num].is_alive = False
        announcement += f"💀 Этой ночью были убиты: {', '.join(map(str, killed_this_night))}.\n"
    else:
        announcement += "🕊 Этой ночью никто не умер!\n"
        
    # --- СВОДКА ПО СЮРИКЕНАМ ---
    # Кто потерял сюрикен за эту ночь (вылечили или сбросил Бессмертный)
    lost_shurikens = [num for num in shurikens_before if game.players_by_number[num].is_alive and game.players_by_number[num].surikens == 0]
    if lost_shurikens:
        announcement += f"🩹 Сюрикены были успешно извлечены (сброшены) у игроков: {', '.join(map(str, lost_shurikens))}\n"

    # На ком сейчас висят сюрикены (новые и старые)
    current_shurikens = [p.number for p in game.get_alive_players() if p.surikens == 1]
    if current_shurikens:
        announcement += f"🥷 Внимание! По 1 сюрикену сейчас висит на игроках: {', '.join(map(str, current_shurikens))}\n"
        
    await bot.send_message(chat_id, announcement)

    if await check_victory(game, chat_id): return

    game.day_count += 1
    game.state = "DAY"
    await start_day_phase(game, chat_id)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

#саня лох
