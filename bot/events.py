import random
import time
import telebot
from telebot import types
from database import get_user, get_travel, users, travel_data, get_available_planet, planets, spawn_planet
from config import ENEMY_NAMES, NPC_TYPES, TRAVEL_IMAGES, PLANET_IMAGES, PLANET_TYPES
from combat import start_combat, generate_enemy_mercenaries, generate_npc_enemies
from planets import get_planet_info, discover_planet, get_zone_info, occupy_zone

EVENT_CHANCES = {
    "cartel": 0.25,
    "tusken": 0.20,
    "tusken_leader": 0.05,
    "paik": 0.20,
    "camp": 0.15,
    "nothing": 0.15
}

def generate_event(planet, location_index):
    if planet == "Космос":
        space_events = ["cartel", "asteroid", "planet", "nothing"]
        weights = [0.25, 0.20, 0.19, 0.36]
        event_type = random.choices(space_events, weights=weights)[0]
    else:
        events = list(EVENT_CHANCES.keys())
        weights = list(EVENT_CHANCES.values())
        event_type = random.choices(events, weights=weights)[0]
    
    if event_type == "planet" and planet == "Космос":
        available_planet = get_available_planet()
        if available_planet:
            return {"type": "planet", "planet_name": available_planet}
        else:
            event_type = "nothing"
    
    return {"type": event_type}

def handle_event(bot, uid, event):
    user = get_user(uid)
    travel = get_travel(uid)
    
    if event['type'] == 'nothing':
        return
    
    elif event['type'] in ['cartel', 'tusken', 'tusken_leader', 'paik']:
        handle_enemy_encounter(bot, uid, event['type'])
    
    elif event['type'] == 'camp':
        handle_camp_encounter(bot, uid)
    
    elif event['type'] == 'asteroid':
        handle_asteroid_field(bot, uid)
    
    elif event['type'] == 'planet':
        handle_planet_discovery(bot, uid, event['planet_name'])

def handle_enemy_encounter(bot, uid, enemy_type):
    user = get_user(uid)
    travel = get_travel(uid)
    
    planet_idx = 1 if user['planet'] == 'Корсат' else 0
    loc_emoji = "🌋" if travel.get('location') == 2 else "🏜️"
    
    if enemy_type == "cartel":
        enemy_name = random.choice(ENEMY_NAMES)
        description = f"_На вашем пути встал вражеский картель. Похоже, они не настроены дружелюбно._"
        escape_chance = 35
    elif enemy_type == "tusken":
        enemy_name = "Таскенские Рейдеры"
        description = f"_Из-за дюн показались фигуры таскенских рейдеров. Их банда выглядит опасной._"
        escape_chance = 40
    elif enemy_type == "tusken_leader":
        enemy_name = "Отряд таскенов с лидером"
        description = f"_Это не обычные рейдеры. Среди них виден опытный лидер, командир отряда._"
        escape_chance = 30
    else:  # paik
        enemy_name = "Отряд Пайков"
        description = f"_Группа пайков перегородила путь. Они выглядят недовольными вашим присутствием._"
        escape_chance = 45
    
    text = f"*{loc_emoji} Путешествуя по поверхности планеты, ты наткнулся на {enemy_name}*\n{description}\n\n🍂 Шанс побега: {escape_chance}%"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if enemy_type == "paik":
        price = random.randint(50, 150)
        travel['combat_data'] = {'enemy_type': enemy_type, 'price': price}
        markup.add(
            types.InlineKeyboardButton("⚔️ Атаковать", callback_data="combat_attack"),
            types.InlineKeyboardButton("💰 Торговаться", callback_data="combat_trade")
        )
    else:
        travel['combat_data'] = {'enemy_type': enemy_type}
        markup.add(
            types.InlineKeyboardButton("⚔️ Атаковать", callback_data="combat_attack"),
            types.InlineKeyboardButton("🏃 Отступить", callback_data=f"combat_escape_{escape_chance}")
        )
    
    msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    travel['message_id'] = msg.message_id
    travel['in_combat'] = True
    travel['combat_data']['timeout'] = time.time() + 60

def handle_camp_encounter(bot, uid):
    user = get_user(uid)
    travel = get_travel(uid)
    
    text = "*⛺️ Твой картель наткнулся на полуразрушенный, похоже уже давно заброшенный лагерь*\n_Что приказешь делать?_"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Обыскать", callback_data="camp_search"),
        types.InlineKeyboardButton("🏕️ Разбить лагерь", callback_data="camp_setup"),
        types.InlineKeyboardButton("🚶 Пройти мимо", callback_data="camp_ignore")
    )
    
    msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    travel['message_id'] = msg.message_id

def handle_asteroid_field(bot, uid):
    user = get_user(uid)
    travel = get_travel(uid)
    
    text = "☄️ *Астероидное поле, берегись столкновения!*\n_Пролетая через это опасное место, можно потерять несколько наемников. Но может быть, все обойдется?_"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Корабль преодолеет поле через: 0м 59с", callback_data="asteroid_timer"))
    
    msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    travel['message_id'] = msg.message_id
    
    import threading
    thread = threading.Thread(target=asteroid_thread, args=(bot, uid))
    thread.daemon = True
    thread.start()

def asteroid_thread(bot, uid):
    time.sleep(59)
    
    user = get_user(uid)
    travel = get_travel(uid)
    
    if random.random() < 0.15:
        from database import user_mercenaries
        mercs = user_mercenaries.get(uid, [])
        if mercs:
            losses = min(random.randint(1, 3), len(mercs))
            user_mercenaries[uid] = mercs[:-losses] if losses > 0 else mercs
            
            text = f"*☄️ Корабль картеля преодолел астероидное поле!*\n_Во время турбулентности погибло {losses} наемников! По прибытии придется пополнить отряды и дать отдохнуть остальным._"
        else:
            text = "*☄️ Корабль картеля преодолел астероидное поле!*\n_Никто не пострадал. Кажется, пора домой._"
    else:
        text = "*☄️ Корабль картеля преодолел астероидное поле!*\n_Никто не пострадал. Кажется, пора домой._"
    
    if travel['message_id']:
        try:
            bot.delete_message(uid, travel['message_id'])
        except:
            pass
    
    bot.send_message(uid, text, parse_mode="Markdown")
    
    from travel import finish_travel
    finish_travel(uid, bot)

def handle_planet_discovery(bot, uid, planet_name):
    user = get_user(uid)
    travel = get_travel(uid)
    
    planet = planets[planet_name]
    planet_type = PLANET_TYPES[planet['type']]
    
    text = f"🌍 *Впереди виднеется планета Внешнего Кольца…*\n_Похоже, что это - {planet_name}!\n\nТебе очень повезло встретить планету, далеко не каждый их находит. Что приказешь делать?_"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛬 Высадиться", callback_data=f"planet_land_{planet_name}"),
        types.InlineKeyboardButton("🏠 Лететь домой", callback_data="planet_go_home")
    )
    
    bot.send_photo(uid, PLANET_IMAGES[planet_type['image_idx']], caption=text, parse_mode="Markdown", reply_markup=markup)
    travel['event'] = {'type': 'planet_discovery', 'planet': planet_name}

def handle_camp_choice(bot, call, choice):
    uid = call.message.chat.id
    user = get_user(uid)
    travel = get_travel(uid)
    
    try:
        bot.delete_message(uid, call.message.message_id)
    except:
        pass
    
    if choice == "search":
        if random.random() < 0.15:
            coins = random.randint(11, 54)
            user['coins'] += coins
            text = f"⛺️ *Обыскав лагерь, твой картель обнаружил следующее:*\n\n+ 💰 {coins} Кредитов\n_Решив больше здесь не задерживаться, картель продолжает путь_"
        else:
            text = "⛺️ *Обыскав лагерь, твой картель ничего не нашел.*\n_Решив больше здесь не задерживаться, картель продолжает путь_"
        
        bot.send_message(uid, text, parse_mode="Markdown")
    
    elif choice == "setup":
        travel['end_time'] += 240  # +4 минуты к путешествию
        text = "⛺️ *Твой картель разбил лагерь на месте старого, чтобы посидеть у костра и набраться сил.*\n_Ты сможешь продолжить путешествие через 2м 59с_"
        
        markup = types.InlineKeyboardMarkup()
        mins = 2
        secs = 59
        markup.add(types.InlineKeyboardButton(f"Продолжить через {mins}м {secs}с", callback_data="camp_continue"))
        
        msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
        travel['message_id'] = msg.message_id
        
        import threading
        thread = threading.Thread(target=camp_rest_thread, args=(bot, uid))
        thread.daemon = True
        thread.start()
    
    elif choice == "ignore":
        text = "⛺️ *Ты решил не тратить время на этот лагерь и продолжил путь.*"
        bot.send_message(uid, text, parse_mode="Markdown")

def camp_rest_thread(bot, uid):
    time.sleep(179)  # 2м 59с
    
    user = get_user(uid)
    travel = get_travel(uid)
    
    if travel['message_id']:
        try:
            bot.delete_message(uid, travel['message_id'])
        except:
            pass
    
    if random.random() < 0.5:
        event = generate_event(user['planet'], travel.get('location', 0))
        if event and event['type'] != 'camp' and event['type'] != 'nothing':
            handle_event(bot, uid, event)
            return
    
    from travel import finish_travel
    finish_travel(uid, bot)

def handle_planet_landing(bot, call, planet_name):
    uid = call.message.chat.id
    user = get_user(uid)
    
    planet = planets[planet_name]
    planet_type = PLANET_TYPES[planet['type']]
    
    info = f"{planet_type['emoji']} *{planet_name}*\n\n🦤 Жизнь: {planet['life']}\n🌱 Климат: {planet_type['climate']}\n💢 Статус: {planet_type['difficulty']}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛬 Высадиться", callback_data=f"planet_choose_zone_{planet_name}"),
        types.InlineKeyboardButton("🏠 Вернуться домой", callback_data="planet_go_home")
    )
    
    bot.send_photo(uid, PLANET_IMAGES[planet_type['image_idx']], caption=info, parse_mode="Markdown", reply_markup=markup)

def handle_planet_zones(bot, call, planet_name):
    uid = call.message.chat.id
    
    text = f"{PLANET_TYPES[planets[planet_name]['type']]['emoji']} *Выбери зону для высаживания*\n_Если есть свободная зона - лучше выбрать ее. Картели, чьи зоны уже заняты, могут жестко ответить на *вторжение*, _даже просто за нахождение в их воздушном пространстве_"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for zone in [1, 2, 3, 4]:
        zone_status, zone_owner = get_zone_info(planet_name, zone)
        if zone_owner:
            owner_cartel = users[zone_owner]['cartel'] if zone_owner in users else "Неизвестно"
            btn_text = f"{'🎪' if zone_owner in users else '🔰'} Зона {zone} ({owner_cartel})"
            callback_data = f"planet_zone_taken_{planet_name}_{zone}"
        else:
            btn_text = f"✨ Зона {zone}"
            callback_data = f"planet_zone_free_{planet_name}_{zone}"
        
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data=f"planet_back_{planet_name}"))
    
    bot.edit_message_caption(
        chat_id=uid,
        message_id=call.message.message_id,
        caption=text,
        parse_mode="Markdown",
        reply_markup=markup
    )

def handle_zone_taken(bot, call, planet_name, zone_num):
    uid = call.message.chat.id
    user = get_user(uid)
    
    zone_status, zone_owner = get_zone_info(planet_name, zone_num)
    
    if not zone_owner:
        occupy_zone(uid, planet_name, zone_num)
        bot.send_message(uid, f"✅ *Ты занял зону {zone_num} на планете {planet_name}!*", parse_mode="Markdown")
        
        from travel import finish_travel
        finish_travel(uid, bot)
        return
    
    owner_policy = users[zone_owner]['policy'] if zone_owner in users else 'aggressive'
    
    if owner_policy == 'aggressive':
        text = f"📍 *Твой картель нарушил воздушное пространство {'картеля' if zone_owner in users else 'альянса'} {users[zone_owner]['cartel'] if zone_owner in users else 'Неизвестно'}*\n_Покинь эту зону в течение 0м 59с, или это будет считаться вторжением!_"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⚔️ Атаковать (⛔️)", callback_data=f"invasion_wait_{planet_name}_{zone_num}"),
            types.InlineKeyboardButton("🏃 Отступить", callback_data="invasion_retreat")
        )
        
        bot.edit_message_caption(
            chat_id=uid,
            message_id=call.message.message_id,
            caption=text,
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        import threading
        thread = threading.Thread(target=invasion_timer, args=(bot, uid, call.message.message_id, planet_name, zone_num))
        thread.daemon = True
        thread.start()
    else:
        text = f"🤝 *Владелец этой зоны настроен дружелюбно.*\n_Ты можешь безопасно пролететь через эту территорию._"
        bot.edit_message_caption(
            chat_id=uid,
            message_id=call.message.message_id,
            caption=text,
            parse_mode="Markdown"
        )
        
        from travel import finish_travel
        finish_travel(uid, bot)

def invasion_timer(bot, uid, msg_id, planet_name, zone_num):
    time.sleep(59)
    
    user = get_user(uid)
    travel = get_travel(uid)
    
    zone_status, zone_owner = get_zone_info(planet_name, zone_num)
    
    if not zone_owner:
        return
    
    from combat import start_invasion
    start_invasion(bot, uid, planet_name, zone_num, zone_owner)

def handle_zone_free(bot, call, planet_name, zone_num):
    uid = call.message.chat.id
    
    success = occupy_zone(uid, planet_name, zone_num)
    
    if success:
        bot.send_message(uid, f"✅ *Ты успешно занял зону {zone_num} на планете {planet_name}!*\n\n🌍 *Теперь ты — Лидер своей зоны!*\n_Это значит, что ты можешь управлять ей как захочешь. Берегись _*вторжений*_ и наращивай мощь!_", parse_mode="Markdown")
        
        from main import show_main_menu
        show_main_menu(bot, uid)
        
        from travel import finish_travel
        finish_travel(uid, bot)
    else:
        bot.send_message(uid, "❌ *Не удалось занять зону. Возможно, она уже занята.*", parse_mode="Markdown")
