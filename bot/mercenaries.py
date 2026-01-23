import telebot
from telebot import types
from database import get_mercenaries, user_mercenaries, users, get_user
import config

def show_mercenaries(bot, msg, page=0):
    uid = msg.chat.id
    user = get_user(uid)
    
    if user['traveling']:
        bot.send_message(uid, "🤺 *Нельзя открыть во время путешествия*", parse_mode="Markdown")
        return
    
    is_tutorial = not user['done']
    merc_data = get_mercenaries(uid, is_tutorial)
    mercs = merc_data['list']
    pages = merc_data['pages']
    
    start = page*8
    end = min(start+8, len(mercs))
    
    text = f"🤺 *Наемники* (2ч 59м)\n_Здесь каждый день собирается много народу - как опытные головорезы, так и новички. Каждый найдет себе подопечных. Разумеется, за хорошую оплату…_\n\nНаемников свободно: {len(mercs)}"
    
    m = types.InlineKeyboardMarkup(row_width=1)
    for merc in mercs[start:end]:
        m.add(types.InlineKeyboardButton(f"{merc['emoji']} {merc['name']}", callback_data=f"m{merc['id']}"))
    
    if pages > 1:
        btns = []
        if page > 0:
            btns.append(types.InlineKeyboardButton("◀️", callback_data=f"merc_page_{page-1}"))
        btns.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="none"))
        if page < pages-1:
            btns.append(types.InlineKeyboardButton("▶️", callback_data=f"merc_page_{page+1}"))
        m.row(*btns)
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=m)

def show_merc_info(bot, call, merc_id):
    uid = call.message.chat.id
    user = get_user(uid)
    is_tutorial = not user['done']
    merc_data = get_mercenaries(uid, is_tutorial)
    merc = merc_data['list'][merc_id]
    page = merc_id // 8
    
    text = f"*{merc['emoji']} {merc['name']} — {merc['class']}*\n\n🫀 Здоровье: {merc['health']}\n💪 Урон: {merc['damage']}\n🧿 Эффективность: {int(merc['efficiency']*100)}%\n\n_Стоимость найма: *{merc['cost']}* кредитов_"
    
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("💰 Нанять", callback_data=f"hire_{merc_id}_{page}"),
        types.InlineKeyboardButton("◀️ Назад", callback_data=f"back_{page}")
    )
    
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=m)

def hire_mercenary(bot, call, merc_id, page):
    uid = call.message.chat.id
    user = get_user(uid)
    is_tutorial = not user['done']
    merc_data = get_mercenaries(uid, is_tutorial)
    merc = merc_data['list'][merc_id]
    
    if uid not in user_mercenaries:
        user_mercenaries[uid] = []
    
    if merc['cost'] > user['coins']:
        bot.answer_callback_query(call.id, "❌ Недостаточно кредитов!")
        return
    
    if merc_id in user_mercenaries[uid]:
        bot.answer_callback_query(call.id, "❌ Уже нанят!")
        return
    
    user_mercenaries[uid].append(merc_id)
    user['coins'] -= merc['cost']
    
    cartel = user['cartel'] or "Без названия"
    bot.send_message(uid, f"*{merc['emoji']} {merc['name']} присоединился к картелю {cartel}!*", parse_mode="Markdown")
    
    if not user['done'] and len(user_mercenaries[uid]) >= 3:
        finish_tutorial(bot, uid)
    else:
        show_mercenaries_page(bot, uid, page)

def show_mercenaries_page(bot, uid, page):
    user = get_user(uid)
    is_tutorial = not user['done']
    merc_data = get_mercenaries(uid, is_tutorial)
    mercs = merc_data['list']
    pages = merc_data['pages']
    
    start = page*8
    end = min(start+8, len(mercs))
    
    text = f"🤺 *Наемники* (2ч 59м)\n_Здесь каждый день собирается много народу - как опытные головорезы, так и новички. Каждый найдет себе подопечных. Разумеется, за хорошую оплату…_\n\nНаемников свободно: {len(mercs)}"
    
    m = types.InlineKeyboardMarkup(row_width=1)
    for merc in mercs[start:end]:
        m.add(types.InlineKeyboardButton(f"{merc['emoji']} {merc['name']}", callback_data=f"m{merc['id']}"))
    
    if pages > 1:
        btns = []
        if page > 0:
            btns.append(types.InlineKeyboardButton("◀️", callback_data=f"merc_page_{page-1}"))
        btns.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="none"))
        if page < pages-1:
            btns.append(types.InlineKeyboardButton("▶️", callback_data=f"merc_page_{page+1}"))
        m.row(*btns)
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=m)

def finish_tutorial(bot, uid):
    user = get_user(uid)
    user['done'] = True
    user['coins'] += 300
    
    text = "📯 *Обучение завершено!*\n\n*🤖 С25-Х*: _Поздравляю! Теперь ты настоящий дайме. Не забудь проверить раздел *Наемники*, чтобы пополнить отряд, и отправляйся в свое первое *Путешествие*!_"
    
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("📕 Другие механики", callback_data="other_mech"))
    
    from main import show_main_menu
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=m)
    show_main_menu(bot, uid)
