import random
import time
from database import planets, spawn_planet, get_available_planet, take_planet_from_queue
from config import PLANET_TYPES, PLANET_IMAGES, PLANET_NAMES

def get_planet_info(planet_name):
    if planet_name not in planets:
        return None
    
    planet = planets[planet_name]
    planet_type = PLANET_TYPES[planet['type']]
    
    info = (
        f"{planet_type['emoji']} *{planet_name}*\n\n"
        f"🦤 Жизнь: {planet['life']}\n"
        f"🌱 Климат: {planet_type['climate']}\n"
        f"💢 Статус: {planet_type['difficulty']}"
    )
    
    return info, planet_type['image_idx']

def check_planet_encounter():
    spawn_planet()
    return random.random() < 0.19056

def discover_planet(uid, planet_name):
    if planet_name not in planets:
        return False
    
    planet = planets[planet_name]
    if not planet['discovered']:
        planet['discovered'] = True
        planet['discovered_by'] = uid
        planet['discovery_date'] = time.time()
        return True
    
    return False

def get_zone_info(planet_name, zone_num):
    if planet_name not in planets:
        return "Свободна", None
    
    planet = planets[planet_name]
    zone_owner = planet['zones'].get(zone_num)
    
    if not zone_owner:
        return "Свободна", None
    
    from database import users
    if zone_owner in users:
        return f"🎪 {users[zone_owner]['cartel']}", zone_owner
    
    return "Занята", zone_owner

def occupy_zone(uid, planet_name, zone_num):
    if planet_name not in planets:
        return False
    
    planet = planets[planet_name]
    if planet['zones'].get(zone_num):
        return False
    
    planet['zones'][zone_num] = uid
    from database import users
    users[uid]['zone'] = zone_num
    users[uid]['planet'] = planet_name
    
    return True

def get_planet_emoji(planet_name):
    if planet_name not in planets:
        return "🌍"
    return PLANET_TYPES[planets[planet_name]['type']]['emoji']
