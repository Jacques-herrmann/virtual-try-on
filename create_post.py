import os
import json
import glob
import time
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

# ── Configuration du logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

VINTED_BASE_URL = "https://www.vinted.fr"
LOGIN_URL = f"{VINTED_BASE_URL}/member/signup/select_type?ref_url=%2F"
SELL_URL = f"{VINTED_BASE_URL}/items/new"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
WAIT_TIMEOUT = 15
LONG_WAIT_TIMEOUT = 30
SHORT_PAUSE = 1.5
MEDIUM_PAUSE = 3
LONG_PAUSE = 5

EMAIL = "jacquesherrmann+belleseconde@gmail.com"
PASSWORD = "***REMOVED***"

ANNONCES_ROOT = r'C:\Users\jhn12\Twake\Annonces\batch\output'

class VintedDraftCreator:
    """Crée des brouillons d'annonces Vinted à partir de dossiers locaux."""

    def __init__(self, headless: bool = False):
        self.driver = None
        self.wait = None
        self.headless = headless
        self._init_driver()


    def _init_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if self.headless:
            options.add_argument("--headless=new")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        self.wait = WebDriverWait(self.driver, WAIT_TIMEOUT)
        self.long_wait = WebDriverWait(self.driver, LONG_WAIT_TIMEOUT)
        logger.info("Driver Chrome initialisé avec succès.")


    def _accept_cookies(self):
        try:
            cookie_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            cookie_btn.click()
            logger.info("Cookies acceptés.")
            time.sleep(SHORT_PAUSE)
        except TimeoutException:
            logger.debug("Pas de bannière de cookies détectée.")

    def _close_popups(self):
        popup_selectors = [
            "[data-testid='modal-close-button']",
            "[aria-label='Fermer']",
            "[aria-label='Close']",
            ".web_ui__Modal__close-button",
        ]
        for selector in popup_selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed():
                    btn.click()
                    logger.debug(f"Pop-up fermé via : {selector}")
                    time.sleep(0.5)
            except (NoSuchElementException, ElementClickInterceptedException):
                continue

    def connect(self, email: str, password: str):
        logger.info("Connexion à Vinted en cours…")
        self.driver.get(LOGIN_URL)
        time.sleep(MEDIUM_PAUSE)

        self._accept_cookies()
        self._close_popups()

        try:
            try:
                login_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//span[@data-testid='auth-select-type--register-switch']/span")
                    )
                )
                login_btn.click()
                time.sleep(SHORT_PAUSE)
                email_login_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//a[contains(@href, 'login?ref_url')]"
                                   " | //button[contains(text(), 'e-mail')]"
                                   " | //span[contains(text(), 'e-mail')]/..")
                    )
                )
                email_login_btn.click()
                time.sleep(SHORT_PAUSE)
            except TimeoutException:
                logger.debug("Pas de bouton 'Continuer avec e-mail' — formulaire direct.")

            email_field = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[name='username'], input[type='email'], input[name='email']")
                )
            )
            email_field.clear()
            email_field.send_keys(email)
            logger.info("Email saisi.")

            password_field = self.driver.find_element(
                By.CSS_SELECTOR, "input[name='password'], input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(password)
            logger.info("Mot de passe saisi.")

            time.sleep(SHORT_PAUSE)

            login_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            login_button.click()
            logger.info("Bouton de connexion cliqué.")

            time.sleep(LONG_PAUSE)
            self._close_popups()

            if "login" not in self.driver.current_url.lower():
                logger.info("✅ Connexion réussie !")
            else:
                logger.warning("⚠️  Connexion peut-être échouée — vérifiez manuellement.")
                # Pause pour permettre la résolution manuelle de CAPTCHA, etc.
                input("Appuyez sur Entrée une fois connecté manuellement…")

        except TimeoutException as e:
            logger.error(f"Timeout lors de la connexion : {e}")
            raise

    @staticmethod
    def _load_item_data(folder_path: str) -> dict:
        """Charge le fichier description.json du dossier."""
        json_path = os.path.join(folder_path, "description.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Fichier description.json introuvable dans {folder_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
        logger.info(f"Données chargées : {data.get('title', 'Sans titre')}")
        return data

    @staticmethod
    def _get_image_paths(folder_path: str) -> list[str]:
        """Récupère tous les chemins d'images du dossier, triés par nom."""
        images = []
        for ext in IMAGE_EXTENSIONS:
            images.extend(glob.glob(os.path.join(folder_path, f"*{ext}")))
            images.extend(glob.glob(os.path.join(folder_path, f"*{ext.upper()}")))
        images = sorted(set(images))
        if not images:
            raise FileNotFoundError(f"Aucune image trouvée dans {folder_path}")
        logger.info(f"{len(images)} image(s) trouvée(s) dans {folder_path}")
        return images

    def _upload_photos(self, image_paths: list[str]):
        """Upload les photos via l'input file caché."""
        try:
            # Vinted utilise un input[type='file'] pour l'upload
            file_input = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[type='file']")
                )
            )

            # Joindre tous les chemins avec \n pour upload multiple
            absolute_paths = [os.path.abspath(p) for p in image_paths]
            all_paths = "\n".join(absolute_paths)

            file_input.send_keys(all_paths)
            logger.info(f"✅ {len(image_paths)} photo(s) uploadée(s).")

            # Attendre que les images soient chargées
            time.sleep(MEDIUM_PAUSE * len(image_paths))

        except TimeoutException:
            logger.error("Impossible de trouver le champ d'upload de fichier.")
            raise

    # ── Remplissage des champs ────────────────────────────────────────────────

    def _fill_text_field(self, selector: str, value: str, by: By = By.CSS_SELECTOR):
        """Remplit un champ texte après l'avoir trouvé et vidé."""
        if not value:
            return
        try:
            field = self.wait.until(EC.presence_of_element_located((by, selector)))
            field.clear()
            field.send_keys(value)
            time.sleep(0.5)
            logger.debug(f"Champ '{selector}' rempli avec '{value[:30]}…'")
        except TimeoutException:
            logger.warning(f"Champ '{selector}' introuvable — ignoré.")

    def _fill_title(self, title: str):
        """Remplit le champ titre."""
        selectors = [
            "input[name*='title']",
            "#title",
            "[data-testid='title-input']",
            "input[placeholder*='titre']",
            "input[placeholder*='Titre']",
        ]
        for sel in selectors:
            try:
                field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                field.clear()
                field.send_keys(title)
                logger.info(f"Titre saisi : {title}")
                return
            except TimeoutException:
                continue
        logger.warning("Champ titre introuvable.")

    def _fill_description(self, description: str):
        """Remplit le champ description."""
        selectors = [
            "textarea[name*='description']",
            "#description",
            "[data-testid='description-input']",
            "textarea[placeholder*='description']",
            "textarea[placeholder*='décri']",
            "textarea",
        ]
        for sel in selectors:
            try:
                field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                field.clear()
                field.send_keys(description)
                logger.info("Description saisie.")
                return
            except TimeoutException:
                continue
        logger.warning("Champ description introuvable.")

    def _fill_price(self, price: str):
        """Remplit le champ prix."""
        selectors = [
            "input[name*='price']",
            "#price",
            "[data-testid='price-input']",
            "input[placeholder*='prix']",
            "input[placeholder*='Prix']",
            "input[placeholder*='0,00']",
        ]
        for sel in selectors:
            try:
                field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                field.clear()
                field.send_keys(price)
                logger.info(f"Prix saisi : {price}€")
                return
            except TimeoutException:
                continue
        logger.warning("Champ prix introuvable.")

    def _click_dropdown_option(self, button_text: str, option_text: str):
        """Clique sur un bouton dropdown puis sélectionne une option."""
        if not option_text:
            return
        try:
            # Trouver le bouton de la catégorie par son label
            buttons = self.driver.find_elements(
                By.XPATH,
                f"//span[contains(text(), '{button_text}')]/ancestor::button"
                f" | //div[contains(text(), '{button_text}')]/ancestor::button"
                f" | //label[contains(text(), '{button_text}')]"
                f"   /following-sibling::*//button"
            )
            for btn in buttons:
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(0.3)
                    btn.click()
                    time.sleep(SHORT_PAUSE)
                    break

            # Sélectionner l'option
            option = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     f"//span[contains(text(), '{option_text}')]"
                     f" | //div[contains(text(), '{option_text}')]"
                     f" | //li[contains(text(), '{option_text}')]")
                )
            )
            option.click()
            logger.info(f"{button_text} → {option_text} sélectionné.")
            time.sleep(SHORT_PAUSE)

        except (TimeoutException, ElementClickInterceptedException) as e:
            logger.warning(f"Impossible de sélectionner {button_text} → {option_text} : {e}")

    def _select_category(self, category: str):
        """Sélectionne la catégorie de l'article."""
        self._click_dropdown_option("Catégorie", category)

    def _select_brand(self, brand: str):
        """Saisit la marque de l'article."""
        if not brand:
            return
        selectors = [
            "input[name*='brand']",
            "[data-testid='brand-input']",
            "input[placeholder*='marque']",
            "input[placeholder*='Marque']",
        ]
        for sel in selectors:
            try:
                field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                field.clear()
                field.send_keys(brand)
                time.sleep(SHORT_PAUSE)
                # Sélectionner la suggestion si elle apparaît
                try:
                    suggestion = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH,
                             f"//div[contains(@class, 'suggestion')]"
                             f"//span[contains(text(), '{brand}')]"
                             f" | //li[contains(text(), '{brand}')]"
                             f" | //a[contains(text(), '{brand}')]")
                        )
                    )
                    suggestion.click()
                except TimeoutException:
                    field.send_keys(Keys.RETURN)
                logger.info(f"Marque saisie : {brand}")
                return
            except TimeoutException:
                continue
        logger.warning("Champ marque introuvable.")

    def _select_size(self, size: str):
        """Sélectionne la taille."""
        self._click_dropdown_option("Taille", size)

    def _select_condition(self, condition: str):
        """Sélectionne l'état de l'article."""
        self._click_dropdown_option("État", condition)

    def _select_color(self, color: str):
        """Sélectionne la couleur."""
        self._click_dropdown_option("Couleur", color)

    def _select_parcel_size(self, parcel_size: str):
        """Sélectionne la taille du colis."""
        self._click_dropdown_option("colis", parcel_size)

    def _save_as_draft(self):
        """Sauvegarde l'annonce en tant que brouillon."""
        draft_selectors = [
            "//button[contains(text(), 'Enregistrer le brouillon')]",
            "//button[contains(text(), 'brouillon')]",
            "//button[contains(text(), 'Brouillon')]",
            "//button[contains(text(), 'Sauvegarder le brouillon')]",
            "//a[contains(text(), 'Sauvegarder le brouillon')]",
            "//span[contains(text(), 'Sauvegarder le brouillon')]/ancestor::button",
        ]
        for sel in draft_selectors:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(0.3)
                btn.click()
                logger.info("✅ Annonce sauvegardée en brouillon !")
                time.sleep(MEDIUM_PAUSE)
                return True
            except (TimeoutException, ElementClickInterceptedException):
                continue

        logger.warning("⚠️  Bouton de sauvegarde brouillon introuvable.")
        return False

    def process_clothing_item(self, clothing_folder: str):
        """Crée un brouillon d'annonce Vinted pour un article donné."""
        logger.info(f"{'='*60}")
        logger.info(f"📦 Traitement de : {clothing_folder}")
        logger.info(f"{'='*60}")

        # 1. Charger les données
        try:
            data = self._load_item_data(clothing_folder)
            image_paths = self._get_image_paths(clothing_folder)
        except FileNotFoundError as e:
            logger.error(f"❌ {e}")
            return False

        # 2. Naviguer vers la page de création d'annonce
        self.driver.get(SELL_URL)
        time.sleep(LONG_PAUSE)
        self._close_popups()

        # 3. Upload des photos
        try:
            self._upload_photos(image_paths)
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'upload des photos : {e}")

        # 4. Remplir les champs du formulaire
        self._fill_title(data.get("title", ""))
        self._fill_description(data.get("description", ""))

        # # Champs à sélection (dropdowns)
        # self._select_category(data.get("category", ""))
        # self._select_brand(data.get("brand", ""))
        # self._select_size(data.get("size", ""))
        # self._select_condition(data.get("condition", ""))
        # self._select_color(data.get("color", ""))
        #
        # Prix
        # self._fill_price(data.get("price", ""))
        #
        # # Taille du colis
        # self._select_parcel_size(data.get("parcel_size", ""))

        # 5. Sauvegarder en brouillon
        time.sleep(SHORT_PAUSE)
        success = self._save_as_draft()

        if success:
            logger.info(f"✅ Brouillon créé pour : {data.get('title', clothing_folder)}")
        else:
            logger.warning(f"⚠️  Brouillon peut-être non sauvegardé pour : {clothing_folder}")
            # Pause manuelle si nécessaire
            input("Vérifiez le brouillon et appuyez sur Entrée pour continuer…")

        return success


    def process_posts(self, folders: list[str], email: str, password: str):
        logger.info(f"🚀 Début du traitement de {len(folders)} annonce(s).")

        self.connect(email, password)
        time.sleep(LONG_PAUSE)

        results = {"success": [], "failed": []}

        for i, folder in enumerate(folders, 1):
            logger.info(f"\n📋 Article {i}/{len(folders)}")
            try:
                success = self.process_clothing_item(folder)
                if success:
                    results["success"].append(folder)
                else:
                    results["failed"].append(folder)
            except Exception as e:
                logger.error(f"❌ Erreur inattendue pour {folder} : {e}")
                results["failed"].append(folder)

            # Pause entre chaque annonce pour éviter la détection
            if i < len(folders):
                pause = LONG_PAUSE + (i % 3)  # Variation légère
                logger.info(f"⏳ Pause de {pause}s avant le prochain article…")
                time.sleep(pause)

        # Résumé
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 RÉSUMÉ")
        logger.info(f"   ✅ Réussis  : {len(results['success'])}")
        logger.info(f"   ❌ Échoués  : {len(results['failed'])}")
        if results["failed"]:
            for f in results["failed"]:
                logger.info(f"      - {f}")
        logger.info(f"{'='*60}")

        return results

    def close(self):
        """Ferme le navigateur."""
        if self.driver:
            self.driver.quit()
            logger.info("Navigateur fermé.")

def main():

    if os.path.isdir(ANNONCES_ROOT):
        folders = sorted([
            os.path.join(ANNONCES_ROOT, d)
            for d in os.listdir(ANNONCES_ROOT)
            if os.path.isdir(os.path.join(ANNONCES_ROOT, d))
            and os.path.exists(os.path.join(ANNONCES_ROOT, d, "description.json"))
        ])
    else:
        logger.error(f"Le dossier '{ANNONCES_ROOT}' n'existe pas.")
        return

    if not folders:
        logger.warning("Aucun dossier d'article trouvé.")
        return

    logger.info(f"📂 {len(folders)} dossier(s) d'articles trouvé(s) :")
    for f in folders:
        logger.info(f"   → {f}")

    creator = VintedDraftCreator(headless=False)
    try:
        creator.process_posts(folders, email=EMAIL, password=PASSWORD)
    finally:
        creator.close()


if __name__ == "__main__":
    main()