#!/usr/bin/env python3
# youtube_cookie_simulator.py - Version finale robuste

import os, time, random, pickle, functools, builtins
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FFOptions
from selenium.webdriver.firefox.service import Service as FFService
from webdriver_manager.firefox import GeckoDriverManager

# ─── flush stdout immediately ─────────────────────────────────────
print = functools.partial(builtins.print, flush=True)

# ─── CONFIG ───────────────────────────────────────────────────────
COOKIES_PKL      = Path("/app/cookies/youtube_cookies.pkl")
SEARCHES         = [
    "python programming", "machine learning tutorial",
    "web development 2025", "data science projects", 
    "artificial intelligence news"
]
DURATION_MIN     = 15          # watch time per session
PAUSE_MIN_MIN    = 1_440       # 24 h (minutes) 
PAUSE_MIN_MAX    = 1_440
HEADLESS         = os.getenv("HEADLESS", "true").lower() == "true"

def new_driver() -> webdriver.Firefox:
    opts = FFOptions()
    if HEADLESS:
        opts.add_argument("--headless")
    opts.set_preference("dom.webdriver.enabled", False)
    opts.set_preference("useAutomationExtension", False)
    opts.set_preference(
        "general.useragent.override",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    )
    drv = webdriver.Firefox(
        service=FFService(GeckoDriverManager().install()),
        options=opts,
    )
    drv.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    )
    return drv

def load_cookies(driver) -> bool:
    """Charge les cookies avec vérification robuste"""
    if not COOKIES_PKL.exists():
        print("❌ cookies pickle manquant :", COOKIES_PKL)
        return False
    
    # Aller sur YouTube
    driver.get("https://www.youtube.com")
    time.sleep(3)
    
    # Charger les cookies
    with open(COOKIES_PKL, 'rb') as f:
        cookies = pickle.load(f)
    
    print(f"📄 {len(cookies)} cookies dans le fichier pickle")
    
    # Injecter les cookies
    ok = 0
    critical_found = []
    critical_names = ['sapisid', 'apisid', 'hsid', 'ssid', 'sid', 'login_info']
    
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            ok += 1
            
            # Tracker cookies critiques
            cookie_name_lower = cookie.get('name', '').lower()
            if any(crit in cookie_name_lower for crit in critical_names):
                critical_found.append(cookie['name'])
                
        except Exception as e:
            print(f"⚠️ Cookie {cookie.get('name', 'unknown')} échoué: {str(e)[:30]}")
    
    driver.refresh()
    time.sleep(4)
    
    print(f"✅ {ok}/{len(cookies)} cookies chargés")
    print(f"🔑 Cookies critiques: {critical_found}")
    
    # Exiger au moins 3 cookies critiques pour une authentification réussie
    return ok > 0 and len(critical_found) >= 3

def logged_in(driver) -> bool:
    """Vérification stricte de la connexion avec test d'historique"""
    try:
        driver.get("https://www.youtube.com")
        time.sleep(5)
        
        # Test 1: Avatar présent
        avatar_found = False
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-masthead #avatar-btn img#img"))
            )
            avatar_found = True
            print("✅ Avatar détecté")
        except:
            print("❌ Aucun avatar trouvé")
        
        # Test 2: Aller sur la page d'historique
        driver.get("https://www.youtube.com/feed/history")
        time.sleep(5)
        
        # Si on est redirigé vers login, pas connecté
        if "accounts.google.com" in driver.current_url or "signin" in driver.current_url:
            print("❌ Redirigé vers login - pas connecté")
            return False
            
        # Test 3: Chercher des éléments spécifiques à l'historique
        try:
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#contents ytd-video-renderer")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-content-type='history']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-browse[page-subtype='history']"))
                )
            )
            print("🎉 Page d'historique accessible - Connexion confirmée !")
            return True
        except:
            print("❌ Page d'historique inaccessible")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test connexion: {e}")
        return False

def save_cookies(driver):
    pickle.dump(driver.get_cookies(), COOKIES_PKL.open("wb"))
    print("💾 cookies mis à jour")

def do_search(driver, query):
    """Recherche via URL directe avec attentes prolongées"""
    search_query = quote_plus(query)  # Encode proprement les espaces et caractères spéciaux
    url = f"https://www.youtube.com/results?search_query={search_query}"
    
    print(f"🔍 {query}")
    driver.get(url)
    
    # Attendre LONGUEMENT que la page charge
    try:
        # D'abord attendre que la structure de base soit là
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#contents"))
        )
        print("✅ Page de résultats chargée")
        
        # Attendre spécifiquement les conteneurs de vidéos
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
        )
        print("✅ Conteneurs vidéos détectés")
        
        # Attendre encore plus pour le JavaScript
        time.sleep(8)
        
    except Exception as e:
        print(f"⚠️ Timeout lors du chargement: {e}")

def watch_video(driver):
    """Recherche de vidéos avec les sélecteurs corrects"""
    
    # Sélecteur principal basé sur votre HTML
    vids = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer a#video-title")
    print(f"🔍 Trouvé {len(vids)} vidéos avec le sélecteur principal")
    
    if not vids:
        print("⚠️ AUCUNE vidéo trouvée - sauvegarde HTML pour debug")
        try:
            with open("/app/cookies/debug_no_videos.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("📄 Page HTML sauvée dans /app/cookies/debug_no_videos.html")
        except:
            pass
        return
    
    # Sélectionner et cliquer sur une vidéo
    vid = random.choice(vids[:8])  # Parmi les 8 premières
    
    # Le titre est dans l'attribut 'title' selon votre HTML
    title = vid.get_attribute("title") or "Vidéo sans titre"
    title = title[:70]  # Tronquer pour les logs
    
    print(f"📺 {title}")
    
    try:
        # Scroll vers la vidéo et cliquer
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vid)
        time.sleep(1)
        
        vid.click()
        
        # Attendre que la page vidéo charge
        time.sleep(2)
        
        t = random.uniform(10, 25)
        time.sleep(t)
        print(f"⏱️ {t:.1f}s visionnés")
        
    except Exception as e:
        print(f"⚠️ Erreur lors du clic: {e}")

def daily_loop():
    while True:
        drv = new_driver()
        try:
            if not load_cookies(drv) or not logged_in(drv):
                print("❌ non connecté – vérifiez vos cookies.")
                time.sleep(600)  # Attendre 10 min avant de réessayer
                continue
            
            print(f"🚀 session démarrée – {DURATION_MIN} min")
            stop_time = time.time() + DURATION_MIN*60
            
            session_count = 0
            while time.time() < stop_time:
                session_count += 1
                print(f"\n--- Vidéo {session_count} ---")
                
                do_search(drv, random.choice(SEARCHES))
                watch_video(drv)
                
                # Pause entre vidéos
                pause = random.uniform(15, 30)
                print(f"⏸️ pause {pause:.0f}s\n")
                time.sleep(pause)
                
            save_cookies(drv)
            print("✅ session terminée ✔︎")
            
        except Exception as e:
            print(f"⚠️ Erreur dans la session: {e}")
        finally:
            try: drv.quit()
            except: pass

        # Sleep 24h
        pause = random.uniform(PAUSE_MIN_MIN, PAUSE_MIN_MAX)
        print(f"🛌 pause {pause/60:.1f} h jusqu'à la prochaine session\n")
        time.sleep(pause*60)

if __name__ == "__main__":
    daily_loop()
