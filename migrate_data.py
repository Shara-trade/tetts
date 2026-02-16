"""
Skript migracii dannyh iz staroj bazy (farm.db) v novuju (farm_v2.db)
"""
import sqlite3
import json
from datetime import datetime

def migrate_data():
    # Podkljuchaemsja k staroj baze
    try:
        old_db = sqlite3.connect('farm.db')
        old_cursor = old_db.cursor()
        print("[OK] Podkljucheno k staroj baze farm.db")
    except Exception as e:
        print(f"[ERROR] Oshibka podkljuchenija k staroj baze: {e}")
        return
    
    # Podkljuchaemsja k novoj baze
    try:
        new_db = sqlite3.connect('farm_v2.db')
        new_cursor = new_db.cursor()
        print("[OK] Podkljucheno k novoj baze farm_v2.db")
    except Exception as e:
        print(f"[ERROR] Oshibka podkljuchenija k novoj baze: {e}")
        return
    
    migrated = {
        'users': 0,
        'plots': 0,
        'inventory': 0,
        'daily': 0,
        'promo_activations': 0
    }
    
    try:
        # 1. Migracija pol'zovatelej
        print("\n>> Migracija pol'zovatelej...")
        old_cursor.execute("SELECT * FROM users")
        users = old_cursor.fetchall()
        
        for user in users:
            try:
                new_cursor.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, balance, prestige_level, 
                     prestige_multiplier, city_level, total_harvested, total_planted, total_earned,
                     joined_date, last_activity, is_banned, ban_reason, ban_until)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user[0],  # user_id
                    user[1],  # username
                    user[2],  # first_name
                    user[3],  # balance
                    user[4],  # prestige_level
                    user[5],  # prestige_multiplier
                    user[6],  # city_level
                    user[7],  # total_harvested
                    0,        # total_planted (novoe pole)
                    user[3],  # total_earned = balance (primerno)
                    user[8],  # joined_date
                    user[9],  # last_activity
                    user[10], # is_banned
                    user[11] if len(user) > 11 else None,  # ban_reason
                    user[12] if len(user) > 12 else None   # ban_until
                ))
                migrated['users'] += 1
            except Exception as e:
                print(f"  [WARN] Oshibka migracii pol'zovatelja {user[0]}: {e}")
        
        print(f"  [OK] Pereneseno {migrated['users']} pol'zovatelej")
        
        # 2. Migracija grjadok
        print("\n>> Migracija grjadok...")
        old_cursor.execute("SELECT * FROM plots")
        plots = old_cursor.fetchall()
        
        for plot in plots:
            try:
                new_cursor.execute("""
                    INSERT OR REPLACE INTO plots 
                    (id, user_id, plot_number, status, crop_type, planted_time, growth_time_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, plot)
                migrated['plots'] += 1
            except Exception as e:
                print(f"  [WARN] Oshibka migracii grjadki {plot[0]}: {e}")
        
        print(f"  [OK] Pereneseno {migrated['plots']} grjadok")
        
        # 3. Migracija inventarja
        print("\n>> Migracija inventarja...")
        try:
            old_cursor.execute("SELECT * FROM inventory")
            inventory_items = old_cursor.fetchall()
            
            for item in inventory_items:
                try:
                    new_cursor.execute("""
                        INSERT OR REPLACE INTO inventory 
                        (user_id, item_code, quantity)
                        VALUES (?, ?, ?)
                    """, item)
                    migrated['inventory'] += 1
                except Exception as e:
                    print(f"  [WARN] Oshibka migracii inventarja: {e}")
            
            print(f"  [OK] Pereneseno {migrated['inventory']} predmetov inventarja")
        except Exception as e:
            print(f"  [WARN] Tablica inventory ne najdena ili pusta: {e}")
        
        # 4. Migracija ezhednevnyh bonusov
        print("\n>> Migracija ezhednevnyh bonusov...")
        try:
            old_cursor.execute("SELECT * FROM user_daily")
            daily_records = old_cursor.fetchall()
            
            for record in daily_records:
                try:
                    new_cursor.execute("""
                        INSERT OR REPLACE INTO user_daily 
                        (user_id, current_streak, last_claim_date, next_claim_date)
                        VALUES (?, ?, ?, ?)
                    """, record)
                    migrated['daily'] += 1
                except Exception as e:
                    print(f"  [WARN] Oshibka migracii daily: {e}")
            
            print(f"  [OK] Pereneseno {migrated['daily']} zapishej ezhednevnyh bonusov")
        except Exception as e:
            print(f"  [WARN] Tablica user_daily ne najdena ili pusta: {e}")
        
        # 5. Migracija aktivacij promokodov
        print("\n>> Migracija aktivacij promokodov...")
        try:
            old_cursor.execute("SELECT * FROM promo_activations")
            activations = old_cursor.fetchall()
            
            for activation in activations:
                try:
                    new_cursor.execute("""
                        INSERT OR REPLACE INTO promo_activations 
                        (promo_id, user_id, activated_at)
                        VALUES (?, ?, ?)
                    """, activation)
                    migrated['promo_activations'] += 1
                except Exception as e:
                    print(f"  [WARN] Oshibka migracii aktivacii: {e}")
            
            print(f"  [OK] Pereneseno {migrated['promo_activations']} aktivacij promokodov")
        except Exception as e:
            print(f"  [WARN] Tablica promo_activations ne najdena ili pusta: {e}")
        
        # Sohranjajaem izmenenija
        new_db.commit()
        print("\n[OK] Migracija uspeshno zavershena!")
        print(f"\n>> Itogo pereneseno:")
        print(f"  Pol'zovatelej: {migrated['users']}")
        print(f"  Grjadok: {migrated['plots']}")
        print(f"  Predmetov inventarja: {migrated['inventory']}")
        print(f"  Ezhednevnyh bonusov: {migrated['daily']}")
        print(f"  Aktivacij promokodov: {migrated['promo_activations']}")
        
    except Exception as e:
        print(f"\n[ERROR] Oshibka vo vremja migracii: {e}")
        new_db.rollback()
    
    finally:
        old_db.close()
        new_db.close()
        print("\n[OK] Bazy dannyh zakryty")

if __name__ == "__main__":
    print("=" * 50)
    print("ZAPUSK MIGRACII DANNYH")
    print("=" * 50)
    migrate_data()
