import telebot
import random
import time
import threading
from telebot import types
from database import get_user, get_travel, travel_data, users, get_mercenaries
from config import PLANET_TYPES, TRAVEL_IMAGES, LOCATIONS
from states import check_travel_cd
from events import generate_event, handle_event

def start_travel(bot, msg):
    uid = msg.chat.id
    user = get_user(uid)
    
    from states import check_traveling
    if check_traveling(uid):
        bot.send_message(uid, "👊 *Ты уже путешествуешь!*", parse_mode="Markdown")
        return
    
    cd_msg = check_travel_cd(uid)
    if cd_msg:
        bot.send_message(uid, f"🙅‍♂️ *Подожди еще {cd_msg}, чтобы снова отправиться путешествовать*", parse_mode="Markdown")
        return
    
    if user['level'] >= 10:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🏜️ По планете", callback_data="travel_planet"),
            types.InlineKeyboardButton("🌌 По Галактике", callback_data="travel_space")
        )
        bot.send_message(uid, "*📯 Выбери тип путешествия*", parse_mode="Markdown", reply_markup=markup)
    else:
        show_planet_travel(bot, uid)

def show_planet_travel(bot, uid, edit_msg=None):
    user = get_user(uid)
    
    planet_idx = 1 if user['planet'] == 'Корсат' else 0
    planet_emoji = PLANET_TYPES[planet_idx]['emoji']
    locations = LOCATIONS[planet_emoji]
    
    text = f"🏜️ *Путешествие по планете*\n_Выбери куда ты хочешь отправиться со своим картелем_"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    times = ["7-11м", "11-17м", "17-24м"]
    
    for i, location in enumerate(locations):
        markup.add(types.InlineKeyboardButton(f"{location} ({times[i]})", callback_data=f"travel_loc_{i}"))
    
    markup.add(types.InlineKeyboardButton("◀️ Назад", callback_data="travel_back"))
    
    if edit_msg:
        bot.edit_message_text(text, uid, edit_msg.message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

def start_space_travel(bot, call):
    uid = call.message.chat.id
    user = get_user(uid)
    travel = get_travel(uid)
    
    travel_time = random.randint(15, 30) * 60
    
    bot.delete_message(uid, call.message.message_id)
    
    travel['type'] = 'space'
    travel['location'] = None
    travel['end_time'] = time.time() + travel_time
    travel['event'] = None
    travel['in_combat'] = False
    user['traveling'] = True
    
    text = "🌌 *Путешествие по Галактике*\n_Здесь пусто, темно и холодно. Редко встречаются другие флоты, а планеты Внешнего Кольца и вовсе разбросаны за световые годы от Корсата…_"
    
    markup = types.InlineKeyboardMarkup()
    mins = travel_time // 60
    secs = travel_time % 60
    markup.add(types.InlineKeyboardButton(f"Осталось путешествовать {mins}м {secs}с", callback_data="travel_timer"))
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    
    thread = threading.Thread(target=space_travel_thread, args=(bot, uid, travel_time))
    thread.daemon = True
    thread.start()

def space_travel_thread(bot, uid, duration):
    user = get_user(uid)
    travel = get_travel(uid)
    
    time.sleep(duration * 0.4)
    
    if travel['in_combat'] or not user['traveling']:
        return
    
    event = generate_event("Космос", 0)
    if event and event['type'] != 'nothing':
        from events import handle_event
        handle_event(bot, uid, event)
        return
    
    time.sleep(duration * 0.6)
    
    if not travel['in_combat'] and user['traveling']:
        finish_travel(uid, bot)

def start_location_travel(bot, call, loc_index):
    uid = call.message.chat.id
    user = get_user(uid)
    travel = get_travel(uid)
    
    planet_idx = 1 if user['planet'] == 'Корсат' else 0
    planet_emoji = PLANET_TYPES[planet_idx]['emoji']
    locations = LOCATIONS[planet_emoji]
    
    loc_name = locations[loc_index]
    loc_emoji = loc_name[0]
    
    times = [
        random.randint(7 * 60, 11 * 60),
        random.randint(11 * 60, 17 * 60),
        random.randint(17 * 60, 24 * 60)
    ]
    travel_time = times[loc_index]
    
    descriptions = [
        "_На горизонте только песок. Может эти дюны и правда бескрайние?_",
        "_Это ближайший и единственный населенный пункт. По крайней мере, в пределах видимости…_",
        "_Поговаривают, это самая опасная часть планеты. Не многим удается вернуться целыми_"
    ]
    
    bot.delete_message(uid, call.message.message_id)
    
    travel['type'] = 'planet'
    travel['location'] = loc_index
    travel['end_time'] = time.time() + travel_time
    travel['event'] = None
    travel['in_combat'] = False
    user['traveling'] = True
    
    text = f"*Ты отправился в {loc_emoji} {loc_name}*\n{descriptions[loc_index]}"
    
    markup = types.InlineKeyboardMarkup()
    mins = travel_time // 60
    secs = travel_time % 60
    markup.add(types.InlineKeyboardButton(f"Осталось путешествовать {mins}м {secs}с", callback_data="travel_timer"))
    
    bot.send_photo(uid, TRAVEL_IMAGES[planet_idx], caption=text, parse_mode="Markdown", reply_markup=markup)
    
    thread = threading.Thread(target=travel_thread, args=(bot, uid, travel_time, loc_index))
    thread.daemon = True
    thread.start()

def travel_thread(bot, uid, duration, loc_index):
    user = get_user(uid)
    travel = get_travel(uid)
    
    time.sleep(duration * 0.3)
    
    if travel['in_combat'] or not user['traveling']:
        return
    
    event_chance = 0.85 if loc_index < 2 else 0.7
    if random.random() < event_chance:
        event = generate_event(user['planet'], loc_index)
        if event:
            travel['event'] = event
            from events import handle_event
            handle_event(bot, uid, event)
            return
    
    time.sleep(duration * 0.7)
    
    if not travel['in_combat'] and user['traveling']:
        finish_travel(uid, bot)

def finish_travel(uid, bot):
    user = get_user(uid)
    travel = get_travel(uid)
    
    if not user['traveling']:
        return
    
    user['traveling'] = False
    user['travel_cd'] = time.time() + 899
    
    if travel['type'] == 'space':
        exp_gain = random.randint(50, 80)
        coin_gain = random.randint(30, 60)
    else:
        exp_min = [23, 29, 39][travel.get('location', 0)]
        exp_max = [34, 41, 52][travel.get('location', 0)]
        exp_gain = random.randint(exp_min, exp_max)
        coin_gain = random.randint(10, 30)
    
    if travel['in_combat']:
        combat_result = travel.get('combat_data', {}).get('result')
        if combat_result == 'win':
            exp_gain += random.randint(10, 20)
            coin_gain += random.randint(20, 50)
        elif combat_result == 'lose':
            exp_gain = int(exp_gain * 0.3)
            coin_gain = int(coin_gain * 0.5)
    
    user['exp'] += exp_gain
    check_level_up(user)
    user['coins'] += coin_gain
    
    if bot:
        if travel.get('combat_data', {}).get('player_losses', 0) > 0:
            status = f"💀 Потеряно {travel['combat_data'].get('player_losses', 0)} наемников."
        else:
            status = "📯 Картель остался цел. Все наемники живы."
        
        travel_type = "🌌" if travel['type'] == 'space' else "🏜️"
        
        text = (
            f"{travel_type} *Твой картель вернулся на базу!*\n\n"
            f"+ 💰 {coin_gain} *кредитов*\n"
            f"+ 🌟 {exp_gain} *опыта*\n\n"
            f"{status}\n"
            f"_После путешествия, наемникам нужно восстановить силы. Чтобы путешествовать снова, подожди 14м 59с_"
        )
        
        bot.send_message(uid, text, parse_mode="Markdown")
    
    travel['type'] = None
    travel['location'] = None
    travel['end_time'] = 0
    travel['event'] = None
    travel['in_combat'] = False
    travel['combat_data'] = None

def check_level_up(user):
    while user['exp'] >= user['max_exp']:
        user['level'] += 1
        user['exp'] -= user['max_exp']
        user['max_exp'] = int(user['max_exp'] * 1.5)
        user['coins'] += user['level'] * 100
        
        if user['level'] == 10:
            user['coins'] += 500
        
        if user['level'] == 25:
            user['coins'] += 1500

def handle_travel_callback(bot, call):
    uid = call.message.chat.id
    data = call.data
    
    if data == "travel_planet":
        show_planet_travel(bot, uid, call.message)
    elif data == "travel_space":
        user = get_user(uid)
        if user['level'] >= 10:
            start_space_travel(bot, call)
        else:
            bot.answer_callback_query(call.id, "📯 *Доступно с 10 уровня*", show_alert=True)
    elif data == "travel_back":
        start_travel(bot, call.message)
    elif data.startswith("travel_loc_"):
        loc_index = int(data.split("_")[2])
        start_location_travel(bot, call, loc_index)
