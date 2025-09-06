#!/usr/bin/env python3
# setup_cookies_headless.py
# Convertit les cookies exportés (Cookie Editor) en format Selenium et vérifie la connexion YouTube

import os, sys, time, json, pickle, functools, builtins
from pathlib import Path
from typing import List, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FFOptions
from selenium.webdriver.firefox.service import Service as FFService
from webdriver_manager.firefox import GeckoDriverManager

# ─── flush stdout immediately ─────────────────────────────────────
print = functools.partial(builtins.print, flush=True)

# ─── CONFIG ───────────────────────────────────────────────────────
COOKIES_DIR = Path("/app/cookies")
OUTPUT_PICKLE = COOKIES_DIR / "youtube_cookies.pkl"
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

def new_driver() -> webdriver.Firefox:
    """Crée une instance Firefox avec les bonnes options anti-détection"""
    opts = FFOptions()
    if HEADLESS:
        opts.add_argument("--headless")
    
    # Options anti-détection
    opts.set_preference("dom.webdriver.enabled", False)
    opts.set_preference("useAutomationExtension", False)
    opts.set_preference(
        "general.useragent.override",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    )
    
    # Créer le driver
    drv = webdriver.Firefox(
        service=FFService(GeckoDriverManager().install()),
        options=opts,
    )
    
    # Masquer les propriétés webdriver
    drv.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    )
    
    return drv

def load_cookies_from_json(json_path: Path) -> List[Dict[str, Any]]:
    """Charge et convertit les cookies depuis le fichier JSON (Cookie Editor format)"""
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier cookies non trouvé: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        cookies_data = json.load(f)
    
    print(f"📥 Chargé {len(cookies_data)} cookies depuis {json_path.name}")
    
    # Convertir format Cookie Editor → Selenium
    selenium_cookies = []
    
    for cookie in cookies_data:
        # Vérifier les champs requis
        if 'name' not in cookie or 'value' not in cookie:
            continue
        
        # Convertir au format Selenium
        selenium_cookie = {
            'name': cookie['name'],
            'value': cookie['value'],
            'domain': cookie.get('domain', '.youtube.com'),
            'path': cookie.get('path', '/'),
            'secure': cookie.get('secure', False),
            'httpOnly': cookie.get('httpOnly', False)
        }
        
        # Convertir timestamp Cookie Editor (Unix timestamp) → Selenium
        if 'expirationDate' in cookie and cookie['expirationDate']:
            try:
                selenium_cookie['expiry'] = int(float(cookie['expirationDate']))
            except (ValueError, TypeError):
                pass  # Ignorer les dates d'expiration invalides
        
        # S'assurer que le domaine est correct pour les cookies Google/YouTube
        domain = selenium_cookie['domain']
        if not domain or (not domain.endswith('youtube.com') and not domain.endswith('google.com')):
            # Pour les cookies d'authentification, forcer le domaine YouTube
            cookie_name_lower = cookie['name'].lower()
            if any(auth in cookie_name_lower for auth in ['login', 'auth', 'session', 'sapisid', 'hsid', 'sid']):
                selenium_cookie['domain'] = '.youtube.com'
        
        selenium_cookies.append(selenium_cookie)
    
    return selenium_cookies

def inject_cookies(driver: webdriver.Firefox, cookies: List[Dict[str, Any]]) -> int:
    """Injection optimisée pour cookies YouTube uniquement"""
    
    # Aller sur YouTube d'abord
    driver.get("https://www.youtube.com")
    time.sleep(3)
    
    injected = 0
    failed = 0
    critical_cookies = []
    critical_names = ['sapisid', 'apisid', 'hsid', 'ssid', 'sid', 'login_info']
    
    for cookie in cookies:
        try:
            # Nettoyer le cookie pour Selenium
            selenium_cookie = {
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': '.youtube.com',  # Forcer le domaine
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
                'httpOnly': cookie.get('httpOnly', False)
            }
            
            # Ajouter expiry si présent et valide
            if 'expirationDate' in cookie and cookie['expirationDate']:
                try:
                    selenium_cookie['expiry'] = int(float(cookie['expirationDate']))
                except (ValueError, TypeError):
                    pass
            
            driver.add_cookie(selenium_cookie)
            injected += 1
            
            # Tracker les cookies critiques
            cookie_name_lower = cookie['name'].lower()
            if any(crit in cookie_name_lower for crit in critical_names):
                critical_cookies.append(cookie['name'])
                
        except Exception as e:
            failed += 1
            print(f"⚠️ Cookie '{cookie.get('name', 'unknown')}' échoué: {str(e)[:50]}")
    
    print(f"✅ {injected}/{len(cookies)} cookies injectés ({failed} échoués)")
    print(f"🔑 Cookies critiques injectés: {critical_cookies}")
    
    if len(critical_cookies) < 3:
        print("⚠️ ATTENTION: Peu de cookies critiques injectés")
    
    return injected

def check_youtube_login(driver: webdriver.Firefox) -> bool:
    """Vérification améliorée de la connexion YouTube"""
    try:
        # Recharger la page pour appliquer les cookies
        driver.refresh()
        time.sleep(6)  # Plus de temps pour le chargement
        
        # Essayer plusieurs sélecteurs pour l'avatar
        avatar_selectors = [
            "ytd-masthead #avatar-btn img#img",
            "button#avatar-btn img",
            "#avatar img",
            "img[alt*='photo']"
        ]
        
        for selector in avatar_selectors:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                print("🎉 Connexion YouTube détectée !")
                return True
            except:
                continue
                
        # Test alternatif : chercher des éléments qui n'apparaissent que connecté
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[href*='/channel/'], [href*='/@']"))
            )
            print("🎉 Connexion YouTube détectée (méthode alternative) !")
            return True
        except:
            pass
            
        print("❌ Connexion YouTube NON détectée")
        return False
        
    except Exception as e:
        print(f"❌ Erreur vérification connexion: {e}")
        return False
    
def save_cookies_enhanced(driver: webdriver.Firefox, output_path: Path) -> int:
    """Sauvegarde TOUS les cookies sans filtrage"""
    
    # Récupérer TOUS les cookies
    all_cookies = driver.get_cookies()
    
    print(f"🔍 Cookies récupérés: {len(all_cookies)}")
    
    # Sauvegarder directement sans modification
    with open(output_path, 'wb') as f:
        pickle.dump(all_cookies, f)
    
    # Analyse des cookies sauvés
    critical_names = ['sapisid', 'apisid', 'hsid', 'ssid', 'sid', 'login_info']
    critical_found = []
    
    for cookie in all_cookies:
        cookie_name_lower = cookie.get('name', '').lower()
        if any(crit in cookie_name_lower for crit in critical_names):
            critical_found.append(cookie['name'])
    
    print(f"💾 Cookies convertis → {output_path}")
    print(f"📊 Stats: {len(all_cookies)} cookies sauvés")
    print(f"🔑 Cookies critiques sauvés: {critical_found}")
    
    return len(all_cookies)

def main():
    """Fonction principale"""
    if len(sys.argv) != 2:
        print("Usage: python setup_cookies_headless.py <cookies_json_file>")
        print("Exemple: python setup_cookies_headless.py /app/cookies/exported_cookies.json")
        sys.exit(1)
    
    cookies_json_path = Path(sys.argv[1])
    
    print(f"🚀 Setup cookies headless - Firefox")
    print(f"📁 Input: {cookies_json_path}")
    print(f"📁 Output: {OUTPUT_PICKLE}")
    
    # Étape 1: Charger les cookies JSON
    try:
        cookies = load_cookies_from_json(cookies_json_path)
    except Exception as e:
        print(f"❌ Erreur chargement cookies: {e}")
        sys.exit(1)
    
    # Étape 2: Lancer Firefox headless
    print("🌐 Démarrage firefox headless…")
    driver = None
    
    try:
        driver = new_driver()
        
        # Étape 3: Injecter les cookies
        injected_count = inject_cookies(driver, cookies)
        
        if injected_count == 0:
            print("❌ Aucun cookie injecté avec succès")
            sys.exit(1)
        
        # Étape 4: Vérifier la connexion YouTube
        login_success = check_youtube_login(driver)
        
        if not login_success:
            print("⚠️  Connexion YouTube non détectée mais on continue...")
        
        # Étape 5: Sauvegarder les cookies mis à jour
        saved_count = save_cookies_enhanced(driver, OUTPUT_PICKLE)
        
        if saved_count > 0:
            print("✅ Setup terminé avec succès!")
        else:
            print("❌ Échec de la sauvegarde des cookies")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Erreur durant le setup: {e}")
        sys.exit(1)
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    main()
