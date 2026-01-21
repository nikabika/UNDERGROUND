import time
import random
from config import PLANET_TYPES, PLANET_NAMES, MERC_NAMES

# Временное хранилище (в будущем заменить на MongoDB)
users = {}
tutorial_stage = {}
mercenaries_data = {}
user_mercenaries = {}
current_sticker = {}
travel_data = {}
planets = {}
alliances = {}
invites = {}
active_fights = {}
user_hp = {}
planet_queue = []
last_planet_spawn = 0

def get_user(uid):
    if uid not in users:
        users[uid] = {
            'coins': 0,
            'cartel': None,
            'done': False,
            'planet': 'Корсат',
            'alliance': None,
            'level': 1,
            'exp': 0,
            'max_exp': 100,
            'traveling': False,
            'travel_end': 0,
            'travel_cd': 0,
            'zone': None,
            'policy': 'friendly',
            'joined': time.time(),
            'hp': {}  # {merc_id: current_hp}
        }
    return users[uid]

def get_mercenaries(uid, tutorial=False):
    if uid not in mercenaries_data:
        random.seed(uid if not tutorial else uid + 999)
        mercs = []
        
        for i in range(50):
            is_aggressor = random.choice([True, False])
            name = random.choice(MERC_NAMES)
            
            if tutorial:
                emoji = "🔫" if is_aggressor else "🧰"
                clas = "Агрессор" if is_aggressor else "Лекарь"
                health = random.randint(30, 35) if is_aggressor else random.randint(35, 40)
                damage = random.randint(7, 9) if is_aggressor else random.randint(3, 5)
                efficiency = random.randint(40, 60)
                cost = 100
            else:
                emoji = "🔫" if is_aggressor else "🧰"
                clas = "Агрессор" if is_aggressor else "Лекарь"
                health = random.randint(30, 45) if is_aggressor else random.randint(35, 53)
                damage = random.randint(7, 13) if is_aggressor else random.randint(3, 6)
                efficiency = random.randint(35, 98)
                if efficiency > 64:
                    efficiency = random.choices([efficiency, random.randint(65, 98)], weights=[70, 30])[0]
                cost = random.randint(50, 150)
            
            mercs.append({
                'id': i,
                'emoji': emoji,
                'name': name,
                'class': clas,
                'health': health,
                'max_health': health,
                'damage': damage,
                'efficiency': efficiency / 100,
                'cost': cost,
                'power': int(health + damage * (efficiency / 100))
            })
        
        mercenaries_data[uid] = {
            'list': mercs,
            'pages': (len(mercs) + 7) // 8,
            'is_tutorial': tutorial,
            'refresh': time.time() + 10740  # 2ч 59м
        }
    return mercenaries_data[uid]

def get_travel(uid):
    if uid not in travel_data:
        travel_data[uid] = {
            'type': None,
            'location': None,
            'end_time': 0,
            'event': None,
            'in_combat': False,
            'combat_data': None,
            'message_id': None
        }
    return travel_data[uid]

def spawn_planet():
    global last_planet_spawn, planet_queue
    current_time = time.time()
    
    if current_time - last_planet_spawn > 86400:  # Раз в день
        available_names = [name for name in PLANET_NAMES if name not in planets]
        if available_names:
            planet_name = random.choice(available_names)
            planet_type = random.randint(0, 6)
            
            planets[planet_name] = {
                'type': planet_type,
                'emoji': PLANET_TYPES[planet_type]['emoji'],
                'name': planet_name,
                'climate': PLANET_TYPES[planet_type]['climate'],
                'difficulty': PLANET_TYPES[planet_type]['difficulty'],
                'life': "Обнаружена" if random.random() > 0.5 else "Не обнаружена",
                'zones': {1: None, 2: None, 3: None, 4: None},
                'discovered': False,
                'discovered_by': None,
                'discovery_date': None
            }
            planet_queue.append(planet_name)
            last_planet_spawn = current_time
            return planet_name
    return None

def get_available_planet():
    if not planet_queue:
        spawn_planet()
    return planet_queue[0] if planet_queue else None

def take_planet_from_queue():
    if planet_queue:
        return planet_queue.pop(0)
    return None
