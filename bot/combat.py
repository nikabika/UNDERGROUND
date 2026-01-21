import random
import time
import telebot
from telebot import types
from database import get_user, get_travel, travel_data, users, get_mercenaries, user_mercenaries
from config import ENEMY_NAMES, NPC_TYPES

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
        is_aggressor = random.choice([True, False])
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
            'name': npc_info['name'],
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
    for merc_id in user_mercenaries.get(uid, []):
        merc_data = get_mercenaries(uid, user['done'])
        if merc_id < len(merc_data['list']):
            merc = merc_data['list'][merc_id].copy()
            merc['current_hp'] = user['hp'].get(merc_id, merc['health'])
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
        'result': None
    }
    
    planet_idx = 1 if user['planet'] == 'Корсат' else 0
    loc_emoji = "🌋" if travel.get('location') == 2 else "🏜️"
    
    text = (
        f"{loc_emoji} *Картель игрока {user['cartel']} vs {enemy_name}*\n"
        f"_Ожесточенное сражение начинается! Наблюдаем за событиями._\n\n"
        f"_Картель игрока {user['cartel']}:_\n"
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
    
    msg = bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)
    travel['message_id'] = msg.message_id

def combat_round(bot, uid):
    travel = get_travel(uid)
    combat = travel['combat_data']
    
    if not combat or combat['result']:
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
        combat['log'].append(f"{attacker['name']} ({attacker['emoji']} Лекарь) — эффект «{effect}»")
        
        if effect == '✳️ Лечение':
            target = random.choice([m for m in (player_mercs if side == 'player' else enemy_mercs) if m != attacker])
            heal = int(target['max_health'] * 0.05)
            target['current_hp'] = min(target['current_hp'] + heal, target['max_health'])
            combat['log'].append(f"{target['name']} 🫀{target['current_hp']} 🔺(+{heal})")
    else:
        dmg, crit = calculate_damage(attacker, defender)
        defender['health' if side == 'enemy' else 'current_hp'] -= dmg
        
        log_msg = f"{attacker['name']} {'⚔️' if crit else '👊'} → {defender['name']}"
        if defender['health' if side == 'enemy' else 'current_hp'] <= 0:
            log_msg += " 💀"
            if side == 'player':
                combat['player_mercs'].remove(defender)
            else:
                combat['enemy_mercs'].remove(defender)
        else:
            hp = defender['health' if side == 'enemy' else 'current_hp']
            log_msg += f" 🫀{hp}{'🔻' if side == 'player' else '🔺'}"
        
        combat['log'].append(log_msg)
    
    if len(combat['log']) > 5:
        combat['log'] = combat['log'][-5:]
    
    update_combat_message(bot, uid)

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
        f"{loc_emoji} *Картель игрока {user['cartel']} vs {combat['enemy_name']}*\n"
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
    
    if combat['result'] is None:
        import threading
        threading.Timer(1.5, combat_round, args=[bot, uid]).start()

def end_combat(bot, uid):
    travel = get_travel(uid)
    user = get_user(uid)
    combat = travel['combat_data']
    
    if not combat:
        return
    
    player_losses = len([m for m in travel['combat_data']['player_mercs'] if m['current_hp'] <= 0])
    
    if combat['result'] == 'win':
        exp_gain = random.randint(30, 60)
        coin_gain = random.randint(50, 100)
        text = f"*{combat['enemy_name']} разгромлен!*\n\n+ 🧩 {exp_gain} опыта\n+ 💰 {coin_gain} кредитов"
        
        user['exp'] += exp_gain
        user['coins'] += coin_gain
    else:
        text = f"*Твой картель проиграл бой!*\n\n- 💀 Потеряно {player_losses} наемников"
        
        merc_ids = user_mercenaries.get(uid, [])
        if len(merc_ids) > player_losses:
            user_mercenaries[uid] = merc_ids[:-player_losses] if player_losses > 0 else merc_ids
    
    travel['in_combat'] = False
    combat['result'] = combat['result'] or 'draw'
    
    bot.send_message(uid, text, parse_mode="Markdown")
    
    if travel['message_id']:
        try:
            bot.delete_message(uid, travel['message_id'])
        except:
            pass

def auto_attack(uid):
    from main import bot_instance
    if bot_instance:
        travel = get_travel(uid)
        if travel['in_combat'] and not travel['combat_data']['result']:
            travel['combat_data']['result'] = 'auto'
            end_combat(bot_instance, uid)
