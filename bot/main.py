import telebot
from telebot import types
import config
from database import get_user, users
import prolog, travel, mercenaries, planets, alliances, events, combat

bot = telebot.TeleBot(config.TOKEN)

def show_main_menu(bot, uid):
    user = get_user(uid)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    
    buttons = [
        "🎪 Мой картель", "🗺️ Быстрое путешествие", "🕍 Кантина",
        "🤺 Наемники", "🔰 Альянсы", "🧩 Профиль",
        "📕 Гайд", "🏆 Рейтинг", "🗞️ Новости"
    ]
    
    if user.get('zone'):
        planet_emoji = planets.get_planet_emoji(user['planet'])
        buttons.append(f"{planet_emoji} Моя планета")
    
    markup.add(*buttons)
    bot.send_message(uid, "📯 *Ты в главном меню*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_command(msg):
    parts = msg.text.split()
    ref = parts[1] if len(parts) > 1 else None
    prolog.handle_start(bot, msg, ref)

@bot.message_handler(func=lambda m: m.text == "🎪 Мой картель")
def cartel_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    cartel = user['cartel'] or "Без названия"
    player = bot.get_chat(uid).first_name
    
    from database import user_mercenaries, mercenaries_data, user_hp
    
    merc_count = len(user_mercenaries.get(uid, []))
    
    total_power = 0
    alive_count = 0
    
    if uid in user_mercenaries and uid in mercenaries_data:
        for mid in user_mercenaries[uid]:
            if mid < len(mercenaries_data[uid]['list']):
                merc = mercenaries_data[uid]['list'][mid]
                current_hp = user_hp.get(uid, {}).get(mid, merc['health'])
                if current_hp > 0:
                    total_power += merc['power']
                    alive_count += 1
    
    avg_power = total_power // max(alive_count, 1) if alive_count > 0 else 0
    
    text = (
        f"🎪 *{cartel}*\n"
        f"_Дайме этого картеля является {player}_\n\n"
        f"💪 Мощь: *{avg_power}*\n"
        f"💰 Казна: {user['coins']} Кредитов\n"
        f"🤺 Наемники: *{merc_count}* ({alive_count} боеспособны)\n"
        f"🗺️ Система: *{user['planet']}*\n"
        f"🔰 Альянс: *{user['alliance'] or 'Нет'}*"
    )
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and "Моя планета" in m.text)
def my_planet_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    
    if not user.get('zone'):
        bot.send_message(uid, "❌ *У тебя нет своей зоны на планете.*", parse_mode="Markdown")
        return
    
    from database import planets
    if user['planet'] not in planets:
        bot.send_message(uid, "❌ *Информация о планете не найдена.*", parse_mode="Markdown")
        return
    
    planet = planets[user['planet']]
    planet_type = config.PLANET_TYPES[planet['type']]
    
    policy_text = "Агрессивная" if user['policy'] == 'aggressive' else "Дружелюбная"
    
    text = (
        f"{planet_type['emoji']} *{user['planet']}*\n\n"
        f"🦤 Жизнь: {planet['life']}\n"
        f"🌱 Климат: {planet_type['climate']}\n"
        f"💢 Статус: {planet_type['difficulty']}\n\n"
        f"🗾 Твоя зона: {user['zone']}\n"
        f"🧑🏼‍✈️ Политика: {policy_text}"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🧑🏼‍✈️ Политика", callback_data="planet_policy"))
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗺️ Быстрое путешествие")
def travel_command(msg):
    travel.start_travel(bot, msg)

@bot.message_handler(func=lambda m: m.text == "🕍 Кантина")
def cantina_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    if user['level'] >= 10:
        bot.send_message(uid, "🕍 *В разработке…*", parse_mode="Markdown")
    else:
        bot.send_message(uid, "📯 *Доступно с 10 уровня*", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔰 Альянсы")
def alliance_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    if user['level'] >= 25:
        if user['alliance']:
            from alliances import get_alliance_info
            info = get_alliance_info(user['alliance'])
            if info:
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("👥 Пригласить участника", callback_data="alliance_invite"),
                    types.InlineKeyboardButton("🚪 Покинуть Альянс", callback_data="alliance_leave")
                )
                bot.send_message(uid, info, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(uid, "❌ *Информация об альянсе не найдена.*", parse_mode="Markdown")
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏗️ Создать альянс", callback_data="alliance_create"))
            bot.send_message(uid, "🔰 *У тебя нет альянса.*\n_Присоединись к существующему или создай свой!_", parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(uid, "📯 *Доступно с 25 уровня*", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🤺 Наемники")
def mercenaries_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    
    from database import user_mercenaries
    from states import check_traveling
    
    if check_traveling(uid):
        bot.send_message(uid, "🤺 *Нельзя открыть во время путешествия*", parse_mode="Markdown")
        return
    
    if not user['done']:
        if len(user_mercenaries.get(uid, [])) >= 3:
            mercenaries.finish_tutorial(bot, uid)
            return
        
        text = (
            "*📯 Поход к наемникам…*\n\n"
            "*🤖 С25-Х*: _Расскажу тебе немного о *Наемниках*! Эти личности - твоя главная рабочая сила. "
            "Когда у тебя есть наемники, тебе не придется в одиночку штурмовать другие картели, путешествовать, "
            "и делать прочие креминальные вещи. Они сделают все за тебя. Но это не бесплатно!_"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Продолжить (1/3)", callback_data="mt1"))
        bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    else:
        mercenaries.show_mercenaries(bot, msg)

@bot.message_handler(func=lambda m: m.text == "🧩 Профиль")
def profile_command(msg):
    uid = msg.chat.id
    user = get_user(uid)
    player = bot.get_chat(uid)
    
    import time
    days = int((time.time() - user['joined']) // 86400)
    hours = int(((time.time() - user['joined']) % 86400) // 3600)
    mins = int(((time.time() - user['joined']) % 3600) // 60)
    
    text = (
        f"🧩 *Профиль игрока {player.first_name}*\n\n"
        f"👤 Юзер: @{player.username or 'нет'}\n"
        f"🆔 Айди: `{uid}`\n"
        f"⏰ Время в игре: {days}д {hours}ч {mins}м\n\n"
        f"🧩 Уровень: {user['level']} ур. ({user['exp']}/{user['max_exp']})\n"
        f"🔰 Альянс: {user['alliance'] or 'Отсутствует'}"
    )
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📕 Гайд")
def guide_command(msg):
    uid = msg.chat.id
    text = "📕 *Сборник гайдов*\n_Здесь - уйма полезной информации! Можно найти что почитать на вечер. Хаха_"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    guides = [
        ("Основы игры", "https://example.com/guide1"),
        ("Система боя", "https://example.com/guide2"),
        ("Планеты и зоны", "https://example.com/guide3"),
        ("Альянсы", "https://example.com/guide4"),
        ("Экономика", "https://example.com/guide5"),
        ("Наемники", "https://example.com/guide6"),
        ("Путешествия", "https://example.com/guide7"),
        ("Советы новичкам", "https://example.com/guide8")
    ]
    
    for name, url in guides:
        markup.add(types.InlineKeyboardButton(name, url=url))
    
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_menu"))
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🏆 Рейтинг")
def rating_command(msg):
    uid = msg.chat.id
    text = "*🏆 Рейтинг игроков на текущий момент*"
    
    from database import users
    sorted_users = sorted(users.items(), key=lambda x: (x[1]['level'], x[1]['coins']), reverse=True)[:10]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i, (uid2, user) in enumerate(sorted_users):
        try:
            name = bot.get_chat(uid2).first_name
            markup.add(types.InlineKeyboardButton(f"{i+1}. {name} 💰{user['coins']} 🧩{user['level']}", callback_data=f"rate_{uid2}"))
        except:
            continue
    
    if len(sorted_users) < 10:
        for i in range(len(sorted_users), 10):
            markup.add(types.InlineKeyboardButton(f"{i+1}. ---", callback_data="none"))
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗞️ Новости")
def news_command(msg):
    uid = msg.chat.id
    text = (
        "🗞️ *Новости АНДЕРГРАУНДА*\n"
        "_Свежие новости появляются здесь не так часто, как хотелось бы…_\n\n"
        "* v0.1 — ALPHA (версия для тестеров выпущена) [16.01.26]\n"
        "* Добавлена механика «ПУТЕШЕСТВИЕ ПО ГАЛАКТИКЕ» [11.01.26]\n"
        "* Добавлен раздел «🗞️ НОВОСТИ» [09.01.26]"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="back_menu"))
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: prolog.tutorial_stage.get(m.chat.id) == 5)
def cartel_name_handler(msg):
    prolog.handle_cartel_name(bot, msg)

@bot.message_handler(func=lambda m: prolog.tutorial_stage.get(m.chat.id) == 6)
def new_cartel_name_handler(msg):
    prolog.handle_new_cartel_name(bot, msg)

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    uid = c.message.chat.id
    
    if c.data.startswith('c'):
        prolog.handle_continue(bot, c)
    elif c.data == "cc":
        prolog.handle_confirm_cartel(bot, c)
    elif c.data == "cf":
        prolog.handle_final_cartel(bot, c)
    elif c.data.startswith('travel'):
        travel.handle_travel_callback(bot, c)
    elif c.data.startswith('m') and c.data[1:].isdigit():
        mercenaries.show_merc_info(bot, c, int(c.data[1:]))
    elif c.data.startswith('merc_page_'):
        page = int(c.data.split('_')[2])
        mercenaries.show_mercenaries_page(bot, uid, page)
    elif c.data.startswith('hire_'):
        parts = c.data.split('_')
        mercenaries.hire_mercenary(bot, c, int(parts[1]), int(parts[2]))
    elif c.data.startswith('back_'):
        page = int(c.data.split('_')[1])
        mercenaries.show_mercenaries_page(bot, uid, page)
    elif c.data.startswith('combat_'):
        combat.handle_combat_callback(bot, c)
    elif c.data.startswith('camp_'):
        events.handle_camp_choice(bot, c, c.data.split('_')[1])
    elif c.data.startswith('planet_'):
        handle_planet_callback(bot, c)
    elif c.data.startswith('invasion_'):
        handle_invasion_callback(bot, c)
    elif c.data.startswith('alliance_'):
        handle_alliance_callback(bot, c)
    elif c.data == "other_mech":
        bot.answer_callback_query(c.id, "Скоро добавим другие механики!")
    elif c.data == "back_menu":
        show_main_menu(bot, uid)
    elif c.data.startswith('mt'):
        stage = int(c.data[2:])
        if stage == 1:
            text = "📯 *Поход к наемникам…*\n\n*🤖 С25-Х*: _Нанимай наемников с умом. Каждые 3 часа приходят новые и уходят старые - так что у тебя будет ограниченное время для выбора. Смотри на показатели и класс. Кроме *Здоровья* и *Урона*, стоит обратить внимание на *Эффективность*. Чем выше этот процент, тем больше будут урон и здоровье твоего наемника в бою!_\n\n_Учти также, что от класса многое зависит. Лекари пока живы - будут поддерживать твоих агрессоров, а агрессоры атаковать врага. Выбирай с умом!_"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Продолжить (2/3)", callback_data="mt2"))
            bot.edit_message_text(text, uid, c.message.message_id, parse_mode="Markdown", reply_markup=markup)
        elif stage == 2:
            users[uid]['coins'] += 300
            text = "📯 *Поход к наемники…*\n\n*🤖 С25-Х*: _Что-ж, я итак уже затянул. Пожалуй, мне не стоит соваться туда. Дальше ты сам! Прежде чем расстаться, возьми эти *300 Кредитов* - они тебе пригодятся! Не экономь и найми трех подопечных. Удачи, начинающий дайме!_"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Продолжить (3/3)", callback_data="mt3"))
            bot.edit_message_text(text, uid, c.message.message_id, parse_mode="Markdown", reply_markup=markup)
        elif stage == 3:
            mercenaries.show_mercenaries(bot, c.message)

def handle_planet_callback(bot, call):
    uid = call.message.chat.id
    data = call.data
    
    if data.startswith('planet_land_'):
        planet_name = data.split('_')[2]
        events.handle_planet_landing(bot, call, planet_name)
    
    elif data == "planet_go_home":
        bot.edit_message_caption(
            chat_id=uid,
            message_id=call.message.message_id,
            caption="🌍 *Ты точно хочешь вернуться домой?*\n_Если планета не заселена полностью, у тебя есть возможность забрать себе кусок территории!_",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Отмена", callback_data=f"planet_back_{call.data.split('_')[2] if '_' in call.data else ''}"),
                types.InlineKeyboardButton("Вернуться домой", callback_data="planet_confirm_home")
            )
        )
    
    elif data == "planet_confirm_home":
        from travel import finish_travel
        finish_travel(uid, bot)
    
    elif data.startswith('planet_back_'):
        planet_name = data.split('_')[2]
        events.handle_planet_landing(bot, call, planet_name)
    
    elif data.startswith('planet_choose_zone_'):
        planet_name = data.split('_')[3]
        events.handle_planet_zones(bot, call, planet_name)
    
    elif data.startswith('planet_zone_taken_'):
        parts = data.split('_')
        planet_name = parts[3]
        zone_num = int(parts[4])
        events.handle_zone_taken(bot, call, planet_name, zone_num)
    
    elif data.startswith('planet_zone_free_'):
        parts = data.split('_')
        planet_name = parts[3]
        zone_num = int(parts[4])
        events.handle_zone_free(bot, call, planet_name, zone_num)
    
    elif data == "planet_policy":
        user = get_user(uid)
        
        text = "🧑🏼‍✈️ *Настройки политики твоей Зоны*\n_Выбери тип политики, который тебе ближе._"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("😡 Агрессивная", callback_data="policy_aggressive"),
            types.InlineKeyboardButton("❇️ Дружелюбная", callback_data="policy_friendly"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="policy_back")
        )
        
        bot.edit_message_text(
            text,
            chat_id=uid,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    elif data.startswith('policy_'):
        if data == "policy_aggressive":
            users[uid]['policy'] = 'aggressive'
            text = "😡 *Агрессивный тип*\n_Любой корабль, пересекший воздушное пространство зоны твоего картеля, будет атакован._"
        elif data == "policy_friendly":
            users[uid]['policy'] = 'friendly'
            text = "❇️ *Дружелюбный тип*\n_Твой картель не будет атаковать корабли, пересекающие твое воздушное пространство. Они, в свою очередь, не смогут атаковать тебя._"
        elif data == "policy_back":
            my_planet_command(type('obj', (object,), {'chat': type('obj', (object,), {'id': uid})()}))
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Применить (✅)", callback_data="policy_apply"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="policy_back")
        )
        
        bot.edit_message_text(
            text,
            chat_id=uid,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    elif data == "policy_apply":
        bot.answer_callback_query(call.id, "✅ Политика применена!")
        my_planet_command(type('obj', (object,), {'chat': type('obj', (object,), {'id': uid})()}))

def handle_invasion_callback(bot, call):
    uid = call.message.chat.id
    data = call.data
    
    if data.startswith('invasion_wait_'):
        parts = data.split('_')
        planet_name = parts[2]
        zone_num = int(parts[3])
        
        remaining = 59 - int(time.time() % 60)
        bot.answer_callback_query(call.id, f"⛔️ *У тебя есть время убраться. Чтобы начать вторжение, жди {remaining}с*", show_alert=True)
    
    elif data == "invasion_retreat":
        from travel import finish_travel
        finish_travel(uid, bot)

def handle_alliance_callback(bot, call):
    uid = call.message.chat.id
    data = call.data
    
    if data == "alliance_create":
        bot.send_message(uid, "🔰 *Введи название для нового альянса (3-20 символов):*", parse_mode="Markdown")
        from database import users
        users[uid]['waiting_for_alliance_name'] = True
    
    elif data == "alliance_invite":
        user = get_user(uid)
        if user['alliance']:
            from alliances import generate_invite_code
            code = generate_invite_code(user['alliance'])
            invite_link = f"https://t.me/under_swbot?start=invite_{code}"
            
            text = f"🔰 *Пригласи игрока в Альянс*\n_Используй ссылку ниже. Отправь ее игроку, и когда он по ней перейдет - сможет вступить в Альянс._\n\n`{invite_link}`"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="alliance_back"))
            
            bot.edit_message_text(
                text,
                chat_id=uid,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=markup
            )
    
    elif data == "alliance_leave":
        from alliances import leave_alliance
        success, message = leave_alliance(uid)
        bot.send_message(uid, message, parse_mode="Markdown")
        if success:
            alliance_command(type('obj', (object,), {'chat': type('obj', (object,), {'id': uid})()}))
    
    elif data == "alliance_back":
        alliance_command(type('obj', (object,), {'chat': type('obj', (object,), {'id': uid})()}))

@bot.message_handler(func=lambda m: users.get(m.chat.id, {}).get('waiting_for_alliance_name'))
def handle_alliance_name(msg):
    uid = msg.chat.id
    user = get_user(uid)
    
    alliance_name = msg.text.strip()
    
    from alliances import create_alliance
    success, message = create_alliance(uid, alliance_name)
    
    bot.send_message(uid, message, parse_mode="Markdown")
    
    if success:
        user['waiting_for_alliance_name'] = False
        alliance_command(msg)

if __name__ == "__main__":
    print("🚀 Бот запущен и готов к работе!")
    print(f"🤖 Токен: {'Установлен' if config.TOKEN else 'НЕ НАЙДЕН!'}")
    
    if not config.TOKEN:
        print("❌ ОШИБКА: Токен не найден! Установи переменную окружения TOKEN на Render.")
        exit(1)
    
    bot.polling(none_stop=True)
