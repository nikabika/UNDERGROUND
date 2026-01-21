import telebot
from telebot import types
from database import get_user, users, tutorial_stage, current_sticker
from main import show_main_menu

STICKERS = [
    "CAACAgIAAxkBAAFAvnZpaRl11JL-bpoEZ9Gmp1fGbdzBwQACYooAAna6SUvykGBAQHi7pjgE",
    "CAACAgIAAxkBAAFAvnppaRmFvpG6MqPOh6CUkvI-4sXCNQACMpoAAjB_SEs4lf0gHJ2nkzgE",
    "CAACAgIAAxkBAAFAvnxpaRmSUAioaYAJ_SbjuS9xxsE2LwACYqIAAkXpSUvd5fzcE_tqczgE"
]

def get_sticker(uid):
    if uid not in current_sticker:
        current_sticker[uid] = 0
    else:
        current_sticker[uid] = (current_sticker[uid] + 1) % 3
    return STICKERS[current_sticker[uid]]

def handle_start(bot, msg, ref=None):
    uid = msg.chat.id
    user = get_user(uid)
    
    if ref and ref.startswith('invite_'):
        from alliances import handle_invite
        handle_invite(bot, uid, ref[7:])
        return
    
    if uid in tutorial_stage and tutorial_stage[uid] not in [None, 0, False]:
        bot.send_message(uid, "👊 *Ты уже в обучении*", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        return
    
    if user['done']:
        show_main_menu(bot, uid)
        return
    
    current_sticker[uid] = 0
    tutorial_stage[uid] = 0
    
    bot.send_sticker(uid, get_sticker(uid))
    
    welcome_text = (
        f"📯 *Ты выходишь из вагона и направляешься в сторону проходного пункта*\n\n"
        f"*🤖 С25-Х*: О-о! Новое лицо! Кажется, ты *{msg.from_user.first_name}*! "
        "_Можешь не отвечать. Знаю что да - я уже отсканировал твой номер. "
        "Не стану гадать как тебя занесло в эти до жути криминальные дебри на самом отшибе Галактики… "
        "Но, в любом случае, раз ты уже здесь, чему я не завидую, нужно адаптироваться. "
        "Давай пройдем короткое обучение! Это не займет много времени…_"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Продолжить", callback_data="c1"))
    bot.send_message(uid, welcome_text, parse_mode="Markdown", reply_markup=markup)

def handle_continue(bot, call):
    uid = call.message.chat.id
    stage = int(call.data[1:])
    
    if stage == 1:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Продолжить 👈", callback_data="c2"))
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=markup)
    
    elif stage == 2:
        bot.delete_message(uid, call.message.message_id - 1)
        bot.delete_message(uid, call.message.message_id)
        
        bot.send_sticker(uid, get_sticker(uid))
        
        text = (
            "*📯 Ты последовал за дроидом. Вскоре он привел тебя на оживленную темную улицу*\n\n"
            "*🤖 С25-Х*: _Сейчас мы находимся на Корсате - планете Внешнего Кольца на Дальних Рубежах. "
            "Наверняка ты ничего не слышал об этом месте! Здешние обитатели - в основном беглецы, "
            "наемники и прочие отбросы общества. Так что тебе нет смысла оставаться на нижних уровнях. "
            "Пройдем на взлетную площадку!_"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Продолжить", callback_data="c3"))
        bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    
    elif stage == 3:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Продолжить 👈", callback_data="c4"))
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=markup)
    
    elif stage == 4:
        bot.delete_message(uid, call.message.message_id - 1)
        bot.delete_message(uid, call.message.message_id)
        
        bot.send_sticker(uid, get_sticker(uid))
        
        player_name = bot.get_chat(uid).first_name
        example = f"Картель игрока {player_name}"
        
        text = (
            f"📯 *На улице светло и жарко. Похоже, поверхность планеты в основном пустынная. "
            f"Ближайший населенный пункт находится в сотнях километров отсюда…*\n\n"
            f"*🤖 С25-Х*: _Вот мы и на месте! Как я уже сказал, на Корсате много недобросовестных личностей. "
            f"Но эту сторону медали ты можешь обернуть в свою пользу! "
            f"Раз криминал здесь в почете, давай начнем с *создания твоего собственного картеля*. "
            f"Придумай название и отправь его мне._\n\n"
            f"_Например: `{example}`_"
        )
        
        bot.send_message(uid, text, parse_mode="Markdown")
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(f"Картель игрока {player_name}")
        bot.send_message(uid, "⌨️ *Клавиатура обновлена*", parse_mode="Markdown", reply_markup=markup)
        
        tutorial_stage[uid] = 5

def handle_cartel_name(bot, msg):
    uid = msg.chat.id
    if msg.sticker:
        return
    
    name = msg.text.strip()
    if 3 <= len(name) <= 30:
        users[uid]['cartel'] = name
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(name, callback_data="cc"))
        
        bot.send_message(uid, "Подтверди название картеля:", reply_markup=markup)
        tutorial_stage[uid] = 6

def handle_new_cartel_name(bot, msg):
    uid = msg.chat.id
    if msg.sticker:
        return
    
    name = msg.text.strip()
    if 3 <= len(name) <= 30:
        users[uid]['cartel'] = name
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(name, callback_data="cc"))
        
        bot.send_message(uid, "Подтверди название картеля:", reply_markup=markup)

def handle_confirm_cartel(bot, call):
    uid = call.message.chat.id
    cartel_name = users[uid]['cartel']
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"{cartel_name} 👈", callback_data="cf"))
    bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=markup)

def handle_final_cartel(bot, call):
    uid = call.message.chat.id
    cartel_name = users[uid]['cartel']
    
    bot.delete_message(uid, call.message.message_id)
    
    bot.send_sticker(uid, get_sticker(uid))
    
    text = (
        f"*📯 Картель создан!*\n\n"
        f"*🤖 С25-Х*: _{cartel_name}? Да у тебя нет вкуса! Но ладно, продолжим. "
        f"Ни один картель не обойдется без *рабочей силы*. "
        f"Давай заглянем в раздел *Наемники* и найдем тебе пару-тройку подопечных, для начальных дел!_\n\n"
        f"_В будущем твои наемники будут отображаться в этом же разделе_"
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤺 Наемники")
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    tutorial_stage[uid] = None
