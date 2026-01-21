import random
import time
import telebot
from telebot import types
from database import get_user, get_travel, travel_data, users, get_mercenaries, user_mercenaries, user_hp
from config import ENEMY_NAMES, NPC_TYPES
from events import handle_camp_choice

def calculate_damage(attacker, defender):
    base_dmg = attacker['damage'] + random.randint(-3, 3)
    dmg = max(1, int(base_dmg / 3.2))
    
    crit_chance = (attacker.get('efficiency', 0.5) - defender.get('damage', 10) / 100) / 2
    crit_chance = max(0, min(crit_chance, 0.5))
    
    is_crit = random.random() < crit_chance
    if is_crit:
        dmg = int(dmg * 1.5)
    
    return dmg, is_crit

def generate_enemy_mercenaries(count=5):
    mercs = []
    for i in range(count):
        is_aggressor = random.choice([True, False]) if i < count - 2 else True
        emoji = "🔫" if is_aggressor else "🧰"
        clas = "Агрессор" if is_aggressor else "Лекарь"
        health = random.randint(25, 40) if is_aggressor else random.randint(30, 45)
        damage = random.randint(6, 11) if is_aggressor else random.randint(2, 5)
        efficiency = random.randint(30, 70) / 100
        
        mercs.append({
            'id': i,
            'emoji': emoji,
            'name': f"Наемник {i+1}",
            'class': clas,
            'health': health,
            'max_health': health,
            'damage': damage,
            'efficiency': efficiency
        })
    return mercs

def generate_npc_enemies(npc_type, count):
    npc_info = NPC_TYPES[npc_type]
    enemies = []
    
    for i in range(count):
        if npc_type == "tusken_leader" and i == 0:
            health = random.randint(npc_info['min_hp'], npc_info['max_hp'])
            if health > 20:
                health = random.choices([health, random.randint(21, 30)], weights=[70, 30])[0]
            damage = random.randint(npc_info['min_dmg'], npc_info['max_dmg'])
            efficiency = random.randint(10, 15) / 100
        else:
            health = random.randint(npc_info['min_hp'], npc_info['max_hp'])
            damage = random.randint(npc_info['min_dmg'], npc_info['max_dmg'])
            efficiency = 0
        
        enemies.append({
            'id': i,
            'emoji': npc_info['emoji'],
            'name': npc_info['name'] + (" (Лидер)" if npc_type == "tusken_leader" and i == 0 else ""),
            'class': "Агрессор",
            'health': health,
            'max_health': health,
            'damage': damage,
            'efficiency': efficiency
        })
    
    return enemies

def start_combat(bot, uid, enemy_type, enemy_data=None):
    user = get_user(uid)
    travel = get_travel(uid)
    
    if enemy_type == "cartel":
        enemy_name = random.choice(ENEMY_NAMES)
        enemy_mercs = generate_enemy_mercenaries(random.randint(5, 7))
    else:
        npc_type = enemy_type
        count = random.randint(3, 5)
        enemy_mercs = generate_npc_enemies(npc_type, count)
        enemy_name = f"{NPC_TYPES[npc_type]['name']}{' (Лидер)' if npc_type == 'tusken_leader' else ''}"
    
    player_mercs = []
    merc_data = get_mercenaries(uid, not user['done'])
    
    for merc_id in user_mercenaries.get(uid, []):
        if merc_id < len(merc_data['list']):
            merc = merc_data['list'][merc_id].copy()
            current_hp = user_hp.get(uid, {}).get(merc_id, merc['health'])
            merc['current_hp'] = current_hp
            merc['max_health'] = merc['health']
            player_mercs.append(merc)
    
    if not player_mercs:
        travel['in_combat'] = False
        bot.send_message(uid, "❌ *У тебя нет наемников для боя!*", parse_mode="Markdown")
        return
    
    travel['in_combat'] = True
    travel['combat_data'] = {
        'enemy_type': enemy_type,
        'enemy_name': enemy_name,
        'player_mercs': player_mercs,
        'enemy_mercs': enemy_mercs,
        'round': 0,
        'log': [],
        'start_time': time.time(),
        'timeout': time.time() + 60,
        'result': None,
        'player_losses': 0,
        'enemy_losses': 0
    }
    
    planet_idx = 1 if user['planet'] == 'Корсат' else 0
    loc_emoji = "🌋" if travel.get('location') == 2 else "🏜️"
    
    text = (
        f"{loc_emoji} *Картель игрока {user['cartel'] or 'Без названия'} vs {enemy_name}*\n"
        f"_Ожесточенное сражение начинается! Наблюдаем за событиями._\n\n"
        f"_Картель игрока {user['cartel'] or 'Без названия'}:_\n"
        f"🤺 Наемник (х{len(player_mercs)})\n\n"
        f"_{enemy_name}:_\n"
        f"🤺 Наемник (х{len(enemy_mercs)})\n"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    escape_chance = 35
    markup.add(
        types.InlineKeyboardButton("⚔️ Атаковать", callback_data="combat_attack"),
        types.InlineKeyboardButton("🏃 Отступить", callback_data=f"combat_escape_{escape_chance}")
    )
    
    if enemy_type == "paik":
        markup.add(types.InlineKeyboardButton("💰 Торговаться", callback_data="combat_trade"))
    
    try:
        if travel['message_id']:
            bot.delete_message(uid, travel['message_id'])
    except:
        pass
    
    msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    travel['message_id'] = msg.message_id

def combat_round(bot, uid):
    travel = get_travel(uid)
    if not travel['in_combat'] or not travel['combat_data']:
        return
    
    combat = travel['combat_data']
    
    if combat['result']:
        return
    
    player_mercs = [m for m in combat['player_mercs'] if m['current_hp'] > 0]
    enemy_mercs = [m for m in combat['enemy_mercs'] if m['health'] > 0]
    
    if not player_mercs:
        combat['result'] = 'lose'
        end_combat(bot, uid)
        return
    
    if not enemy_mercs:
        combat['result'] = 'win'
        end_combat(bot, uid)
        return
    
    combat['round'] += 1
    
    attacker = random.choice(player_mercs + enemy_mercs)
    if attacker in player_mercs:
        defender = random.choice(enemy_mercs)
        side = "player"
    else:
        defender = random.choice(player_mercs)
        side = "enemy"
    
    if attacker['class'] == 'Лекарь' and random.random() < 0.45:
        effect = random.choice(['✳️ Лечение', '❎ Сопротивление', '❇️ Реанимация'])
        
        if effect == '✳️ Лечение':
            targets = [m for m in (player_mercs if side == 'player' else enemy_mercs) if m != attacker]
            if targets:
                target = random.choice(targets)
                heal = int(target['max_health'] * 0.05)
                target['current_hp' if side == 'player' else 'health'] = min(
                    target['current_hp' if side == 'player' else 'health'] + heal,
                    target['max_health']
                )
                combat['log'].append(f"{attacker['name']} ({attacker['emoji']}) — {effect} +{heal} HP")
        elif effect == '❎ Сопротивление':
            combat['log'].append(f"{attacker['name']} ({attacker['emoji']}) — {effect}")
        elif effect == '❇️ Реанимация' and attacker['efficiency'] >= 0.6:
            dead_mercs = [m for m in combat['player_mercs'] if m['current_hp'] <= 0] if side == 'player' else [m for m in combat['enemy_mercs'] if m['health'] <= 0]
            if dead_mercs:
                target = random.choice(dead_mercs)
                target['current_hp' if side == 'player' else 'health'] = int(target['max_health'] * 0.5)
                combat['log'].append(f"{attacker['name']} ({attacker['emoji']}) — {effect}")
    else:
        dmg, crit = calculate_damage(attacker, defender)
        
        if side == "player":
            defender['health'] -= dmg
            current_hp = defender['health']
        else:
            defender['current_hp'] -= dmg
            current_hp = defender['current_hp']
        
        log_msg = f"{attacker['name']} {'⚔️' if crit else '👊'} → {defender['name']}"
        
        if current_hp <= 0:
            log_msg += " 💀"
            if side == "player":
                combat['enemy_mercs'].remove(defender)
                combat['enemy_losses'] += 1
            else:
                combat['player_mercs'].remove(defender)
                combat['player_losses'] += 1
        else:
            log_msg += f" 🫀{current_hp}{'🔻' if side == 'enemy' else '🔺'}"
        
        combat['log'].append(log_msg)
    
    if len(combat['log']) > 5:
        combat['log'] = combat['log'][-5:]
    
    update_combat_message(bot, uid)
    
    if not combat['result']:
        import threading
        threading.Timer(1.5, combat_round, args=[bot, uid]).start()

def update_combat_message(bot, uid):
    travel = get_travel(uid)
    if not travel['in_combat'] or not travel['combat_data']:
        return
    
    combat = travel['combat_data']
    user = get_user(uid)
    
    player_alive = len([m for m in combat['player_mercs'] if m['current_hp'] > 0])
    enemy_alive = len([m for m in combat['enemy_mercs'] if m['health'] > 0])
    
    loc_emoji = "🌋" if travel.get('location') == 2 else "🏜️"
    
    text = (
        f"{loc_emoji} *Картель игрока {user['cartel'] or 'Без названия'} vs {combat['enemy_name']}*\n"
        f"_Раунд {combat['round']}_\n\n"
    )
    
    for log in combat['log'][-3:]:
        text += f"{log}\n"
    
    text += f"\n_Живых: {player_alive} vs {enemy_alive}_"
    
    try:
        bot.edit_message_text(
            text,
            chat_id=uid,
            message_id=travel['message_id'],
            parse_mode="Markdown"
        )
    except:
        pass

def end_combat(bot, uid):
    travel = get_travel(uid)
    user = get_user(uid)
    
    if not travel['in_combat'] or not travel['combat_data']:
        return
    
    combat = travel['combat_data']
    
    player_losses = combat['player_losses']
    enemy_losses = combat['enemy_losses']
    
    if uid not in user_hp:
        user_hp[uid] = {}
    
    if combat['result'] == 'win':
        exp_gain = random.randint(30, 60) + enemy_losses * 10
        coin_gain = random.randint(50, 100) + enemy_losses * 20
        
        user['exp'] += exp_gain
        user['coins'] += coin_gain
        
        for merc in combat['player_mercs']:
            if merc['current_hp'] > 0:
                merc_id = next((m['id'] for m in get_mercenaries(uid, not user['done'])['list'] if m['name'] == merc['name'] and m['class'] == merc['class']), None)
                if merc_id is not None:
                    user_hp[uid][merc_id] = merc['current_hp']
        
        text = f"🎊 *Твой картель разгромил {combat['enemy_name']}!*\n\n- 💀 Потеряно {player_losses} наемников\n+ 🧩 {exp_gain} опыта\n+ 💰 {coin_gain} Кредитов"
    
    elif combat['result'] == 'lose':
        exp_gain = int(random.randint(10, 20) * 0.3)
        user['exp'] += exp_gain
        
        merc_ids = user_mercenaries.get(uid, [])
        if len(merc_ids) > player_losses:
            user_mercenaries[uid] = merc_ids[:-player_losses] if player_losses > 0 else merc_ids
            user_hp[uid] = {mid: get_mercenaries(uid, not user['done'])['list'][mid]['health'] for mid in user_mercenaries[uid][:3]}
        elif merc_ids:
            user_mercenaries[uid] = []
            user_hp[uid] = {}
        
        text = f"💢 *Бой завершен! {combat['enemy_name']} одержал победу!*\n\n- 💀 Потеряно {player_losses} наемников\n+ 🧩 {exp_gain} опыта\n_Твой картель был раздавлен, придется вернуться домой ни с чем._"
    
    else:
        text = f"⚖️ *Бой завершился ничьей!*\n\n- 💀 Потеряно с обеих сторон: {player_losses} vs {enemy_losses}\n_Оба картеля отступили, чтобы зализать раны._"
    
    travel['in_combat'] = False
    
    if travel['message_id']:
        try:
            bot.delete_message(uid, travel['message_id'])
        except:
            pass
    
    bot.send_message(uid, text, parse_mode="Markdown")
    
    from travel import finish_travel
    finish_travel(uid, bot)

def handle_combat_callback(bot, call):
    uid = call.message.chat.id
    data = call.data
    
    if data == "combat_attack":
        travel = get_travel(uid)
        if travel['in_combat'] and travel['combat_data']:
            combat_round(bot, uid)
    
    elif data.startswith("combat_escape_"):
        escape_chance = int(data.split("_")[2])
        if random.randint(1, 100) <= escape_chance:
            travel = get_travel(uid)
            travel['in_combat'] = False
            
            if travel['message_id']:
                try:
                    bot.delete_message(uid, travel['message_id'])
                except:
                    pass
            
            loc_emoji = "🌋" if travel.get('location') == 2 else "🏜️"
            bot.send_message(uid, f"{loc_emoji} *Ты успешно отступил от противника!*", parse_mode="Markdown")
            
            from travel import finish_travel
            finish_travel(uid, bot)
        else:
            travel = get_travel(uid)
            if travel['in_combat'] and travel['combat_data']:
                combat_round(bot, uid)
    
    elif data == "combat_trade":
        travel = get_travel(uid)
        user = get_user(uid)
        
        if travel['in_combat'] and travel['combat_data']:
            price = travel['combat_data'].get('price', 100)
            
            text = f"📯 *Ты решил торговаться с пайками*\n_Если ты выплатишь их цену за проезд - останешься целым. Нужно все тщательно обдумать._\n\nПайки требуют за проезд: {price} 💰 Кредитов"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⚔️ Атаковать", callback_data="combat_attack"),
                types.InlineKeyboardButton(f"💰 Заплатить ({price})", callback_data="combat_pay")
            )
            
            bot.edit_message_text(
                text,
                chat_id=uid,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=markup
            )
    
    elif data == "combat_pay":
        travel = get_travel(uid)
        user = get_user(uid)
        
        if travel['in_combat'] and travel['combat_data']:
            price = travel['combat_data'].get('price', 100)
            
            if user['coins'] >= price:
                user['coins'] -= price
                travel['in_combat'] = False
                
                if travel['message_id']:
                    try:
                        bot.delete_message(uid, travel['message_id'])
                    except:
                        pass
                
                bot.send_message(uid, "📯 *Пайки сдержали слово и пропустили твой картель без проблем.*", parse_mode="Markdown")
                
                from travel import finish_travel
                finish_travel(uid, bot)
            else:
                bot.answer_callback_query(call.id, "❌ Недостаточно кредитов!")

def start_invasion(bot, uid, planet_name, zone_num, defender_uid):
    user = get_user(uid)
    defender = get_user(defender_uid) if defender_uid in users else None
    
    if not defender:
        return
    
    player_mercs = []
    merc_data = get_mercenaries(uid, not user['done'])
    
    for merc_id in user_mercenaries.get(uid, []):
        if merc_id < len(merc_data['list']):
            merc = merc_data['list'][merc_id].copy()
            current_hp = user_hp.get(uid, {}).get(merc_id, merc['health'])
            merc['current_hp'] = current_hp
            merc['max_health'] = merc['health']
            player_mercs.append(merc)
    
    defender_mercs = []
    defender_merc_data = get_mercenaries(defender_uid, not defender['done'])
    
    for merc_id in user_mercenaries.get(defender_uid, []):
        if merc_id < len(defender_merc_data['list']):
            merc = defender_merc_data['list'][merc_id].copy()
            current_hp = user_hp.get(defender_uid, {}).get(merc_id, merc['health'])
            merc['current_hp'] = current_hp
            merc['max_health'] = merc['health']
            defender_mercs.append(merc)
    
    if not player_mercs:
        bot.send_message(uid, "❌ *У тебя нет наемников для вторжения!*", parse_mode="Markdown")
        return
    
    text = f"🌌 *Начато вторжение на зону {zone_num} планеты {planet_name}!*\n\n_Ты атакуешь картель {defender['cartel']}. Бой начинается!_"
    bot.send_message(uid, text, parse_mode="Markdown")
    
    invasion_data = {
        'attacker': uid,
        'defender': defender_uid,
        'planet': planet_name,
        'zone': zone_num,
        'player_mercs': player_mercs,
        'defender_mercs': defender_mercs,
        'round': 0,
        'result': None
    }
    
    invasion_combat(bot, invasion_data)

def invasion_combat(bot, invasion_data):
    attacker = invasion_data['attacker']
    defender = invasion_data['defender']
    
    player_mercs = [m for m in invasion_data['player_mercs'] if m['current_hp'] > 0]
    defender_mercs = [m for m in invasion_data['defender_mercs'] if m['current_hp'] > 0]
    
    if not player_mercs:
        invasion_data['result'] = 'defender_win'
        end_invasion(bot, invasion_data)
        return
    
    if not defender_mercs:
        invasion_data['result'] = 'attacker_win'
        end_invasion(bot, invasion_data)
        return
    
    invasion_data['round'] += 1
    
    attacker_unit = random.choice(player_mercs)
    defender_unit = random.choice(defender_mercs)
    
    dmg, crit = calculate_damage(attacker_unit, defender_unit)
    defender_unit['current_hp'] -= dmg
    
    if defender_unit['current_hp'] <= 0:
        invasion_data['defender_mercs'].remove(defender_unit)
    
    dmg2, crit2 = calculate_damage(defender_unit, attacker_unit)
    attacker_unit['current_hp'] -= dmg2
    
    if attacker_unit['current_hp'] <= 0:
        invasion_data['player_mercs'].remove(attacker_unit)
    
    import threading
    threading.Timer(1.0, invasion_combat, args=[bot, invasion_data]).start()

def end_invasion(bot, invasion_data):
    attacker = invasion_data['attacker']
    defender = invasion_data['defender']
    planet_name = invasion_data['planet']
    zone_num = invasion_data['zone']
    
    from database import planets, user_mercenaries, user_hp
    
    if invasion_data['result'] == 'attacker_win':
        attacker_user = get_user(attacker)
        defender_user = get_user(defender)
        
        attacker_losses = len([m for m in invasion_data['player_mercs'] if m['current_hp'] <= 0])
        defender_losses = len([m for m in invasion_data['defender_mercs'] if m['current_hp'] <= 0])
        
        exp_gain = random.randint(190, 230)
        coin_gain = int(defender_user['coins'] * 0.45)
        
        attacker_user['exp'] += exp_gain
        attacker_user['coins'] += coin_gain
        defender_user['coins'] = int(defender_user['coins'] * 0.80)
        
        merc_ids = user_mercenaries.get(defender, [])
        keep_count = max(1, int(len(merc_ids) * 0.15))
        user_mercenaries[defender] = merc_ids[:keep_count] if merc_ids else []
        
        if defender in user_hp:
            user_hp[defender] = {mid: get_mercenaries(defender, not defender_user['done'])['list'][mid]['health'] for mid in user_mercenaries[defender][:3]}
        
        planets[planet_name]['zones'][zone_num] = attacker
        attacker_user['zone'] = zone_num
        attacker_user['planet'] = planet_name
        defender_user['zone'] = None
        defender_user['planet'] = 'Корсат'
        
        bot.send_message(attacker, f"🎊 *Твой картель провел успешное вторжение!\n\n- 💀 Потеряно {attacker_losses} наемников\n+ 🧩 {exp_gain} опыта\n+ 💰 {coin_gain} Кредитов\n\nТеперь зона {zone_num} на планете {planet_name} принадлежит тебе!*", parse_mode="Markdown")
        
        bot.send_message(defender, f"💥 *{attacker_user['cartel']} вторгся на твою территорию!\n\n- 💀 Потеряно {defender_losses} наемников\n- 💰 Потеряно {int(defender_user['coins'] * 0.20)} Кредитов\n\nОстатки твоего картеля отступили обратно на Корсат*", parse_mode="Markdown")
    
    else:
        attacker_user = get_user(attacker)
        defender_user = get_user(defender)
        
        attacker_losses = len([m for m in invasion_data['player_mercs'] if m['current_hp'] <= 0])
        defender_losses = len([m for m in invasion_data['defender_mercs'] if m['current_hp'] <= 0])
        
        exp_gain = random.randint(230, 549)
        coin_gain = int(attacker_user['coins'] * 0.90)
        
        defender_user['exp'] += exp_gain
        defender_user['coins'] += coin_gain
        
        merc_ids = user_mercenaries.get(attacker, [])
        keep_count = max(1, int(len(merc_ids) * 0.05))
        user_mercenaries[attacker] = merc_ids[:keep_count] if merc_ids else []
        
        if attacker in user_hp:
            user_hp[attacker] = {mid: get_mercenaries(attacker, not attacker_user['done'])['list'][mid]['health'] for mid in user_mercenaries[attacker][:3]}
        
        attacker_user['planet'] = 'Корсат'
        
        bot.send_message(attacker, f"💢 *Бой завершен! Картель врага одержал победу!\n\n- 💀 Потеряно {attacker_losses} наемников\n_Твой картель был раздавлен, придется вернуться домой ни с чем._*", parse_mode="Markdown")
        
        bot.send_message(defender, f"🪖 *Вторжение, совершенное {attacker_user['cartel']} было отбито!\n\n- 💀 Потеряно {defender_losses} наемников\n+ 🧩 {exp_gain} опыта\n+ 💰 {coin_gain} кредитов*", parse_mode="Markdown")
    
    from travel import finish_travel
    finish_travel(attacker, bot)
