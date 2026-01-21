import time
from database import get_user, get_travel, users, travel_data

def check_traveling(uid):
    user = get_user(uid)
    travel = get_travel(uid)
    
    if user['traveling']:
        current_time = time.time()
        if current_time > user['travel_end']:
            from travel import finish_travel
            finish_travel(uid, None)  # Бот передается позже
            return False
        
        if travel['in_combat'] and current_time > travel['combat_data'].get('timeout', 0):
            from combat import auto_attack
            auto_attack(uid)
            return True
        
        return True
    return False

def check_travel_cd(uid):
    user = get_user(uid)
    if user['travel_cd'] > 0:
        if time.time() > user['travel_cd']:
            user['travel_cd'] = 0
            return False
        
        remaining = int(user['travel_cd'] - time.time())
        mins = remaining // 60
        secs = remaining % 60
        return f"{mins}м {secs}с"
    return None

def check_combat_timeout(uid):
    travel = get_travel(uid)
    if travel['in_combat'] and travel['combat_data']:
        return travel['combat_data'].get('timeout', 0) < time.time()
    return False
