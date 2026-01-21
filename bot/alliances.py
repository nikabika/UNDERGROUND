import random
import string
import time
from database import alliances, invites, users
from config import PLANET_NAMES

def create_alliance(uid, name):
    if name in alliances:
        return False, "Альянс с таким названием уже существует"
    
    if len(name) < 3 or len(name) > 20:
        return False, "Название должно быть от 3 до 20 символов"
    
    alliances[name] = {
        'leader': uid,
        'members': [uid],
        'created': time.time(),
        'planet_zones': {},
        'power': 0
    }
    
    users[uid]['alliance'] = name
    return True, f"Альянс *{name}* создан!"

def generate_invite_code(alliance_name):
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    invites[code] = {
        'alliance': alliance_name,
        'created': time.time(),
        'uses': 0,
        'max_uses': 5
    }
    return code

def join_alliance(uid, code):
    if code not in invites:
        return False, "Недействительный код приглашения"
    
    invite = invites[code]
    if invite['uses'] >= invite['max_uses']:
        return False, "Код приглашения истек"
    
    if time.time() - invite['created'] > 86400:
        return False, "Код приглашения истек"
    
    alliance_name = invite['alliance']
    if alliance_name not in alliances:
        return False, "Альянс не найден"
    
    if uid in alliances[alliance_name]['members']:
        return False, "Ты уже в этом альянсе"
    
    if len(alliances[alliance_name]['members']) >= 15:
        return False, "Альянс достиг максимального количества участников"
    
    alliances[alliance_name]['members'].append(uid)
    users[uid]['alliance'] = alliance_name
    invite['uses'] += 1
    
    return True, f"Ты вступил в альянс *{alliance_name}*!"

def leave_alliance(uid):
    user = users.get(uid)
    if not user or not user['alliance']:
        return False, "Ты не состоишь в альянсе"
    
    alliance_name = user['alliance']
    if alliance_name not in alliances:
        user['alliance'] = None
        return False, "Альянс не найден"
    
    alliance = alliances[alliance_name]
    if uid in alliance['members']:
        alliance['members'].remove(uid)
    
    if uid == alliance['leader'] and alliance['members']:
        alliance['leader'] = alliance['members'][0]
    elif not alliance['members']:
        del alliances[alliance_name]
    
    user['alliance'] = None
    return True, "Ты покинул альянс"

def get_alliance_info(alliance_name):
    if alliance_name not in alliances:
        return None
    
    alliance = alliances[alliance_name]
    
    from database import users
    member_names = []
    systems = set()
    
    for member_uid in alliance['members'][:5]:
        if member_uid in users:
            member_names.append(users[member_uid]['cartel'] or f"Игрок {member_uid}")
            systems.add(users[member_uid]['planet'])
    
    power = sum([users[uid].get('power', 0) for uid in alliance['members'] if uid in users])
    avg_power = power // max(len(alliance['members']), 1)
    
    systems_list = list(systems)[:3]
    extra = len(systems) - 3
    
    info = (
        f"🔰 *{alliance_name}*\n\n"
        f"💪 Мощь: *{avg_power}*\n"
        f"👤 Участники: {len(alliance['members'])}\n"
        f"🗺️ Системы: {', '.join(systems_list)}{f' (+{extra})' if extra > 0 else ''}"
    )
    
    return info

def handle_invite(bot, uid, code):
    success, message = join_alliance(uid, code)
    bot.send_message(uid, message, parse_mode="Markdown")
