import os
import json
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- AYARLAR ---
# Token'ı buraya yazabilirsin ama Koyeb'de Environment Variable olarak eklemen daha güvenli.
TOKEN = os.getenv("TELEGRAM_TOKEN", "BURAYA_TOKENINI_YAZABILIRSIN")
# İzin verilen kullanıcı ID'leri (Kendi Telegram ID'ni buraya virgülle ayırarak yaz)
ALLOWED_USERS = [5952744818, 98765432]
CHECK_INTERVAL = 300  # Kaç saniyede bir kontrol etsin? (300 saniye = 5 dakika)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Veri Saklama (Basit JSON)
DATA_FILE = "products.json"

# --- YARDIMCI FONKSİYONLAR ---

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_driver():
    """Headless Chrome sürücüsünü başlatır."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Arayüzsüz mod
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Bot algılamayı azaltmak için User-Agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # Sürücüyü otomatik indir ve kur (En önemli kısım burası)
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

# --- SCRAPER MANTIĞI ---

def check_zara_stock(driver, url, target_sizes):
    """Zara için stok kontrolü yapar."""
    try:
        driver.get(url)
        # Sayfanın yüklenmesini bekle
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Olası "Sepete Ekle" butonu veya Beden seçicileri
        stock_found = []
        
        # Zara genelde bedenleri bir button listesi olarak tutar
        # Bu selector değişebilir ama genelde size-selector veya benzeri classlar olur.
        # En garanti yöntem metin taramasıdır.
        
        page_source = driver.page_source
        
        for size in target_sizes:
            # Basit mantık: Eğer bedenin yanında "Out of stock" veya "Tükendi" yazmıyorsa ve tıklanabilirse
            # Zara HTML yapısı sık değişir, bu yüzden geniş bir arama yapıyoruz.
            # Burada 'size-in-stock' class'ına bakıyoruz (senin eski kodundaki gibi)
            try:
                # Beden butonlarını bulmaya çalış
                elements = driver.find_elements(By.XPATH, f"//span[contains(text(), '{size}')]/ancestor::li")
                if not elements:
                    elements = driver.find_elements(By.XPATH, f"//div[contains(@class, 'size') and contains(text(), '{size}')]")
                
                # Eğer element bulunduysa class kontrolü yap
                for el in elements:
                    if "disabled" not in el.get_attribute("class") and "out-of-stock" not in el.get_attribute("class"):
                        stock_found.append(size)
                        break
            except:
                continue
                
        return stock_found
    except Exception as e:
        logger.error(f"Zara hata: {e}")
        return []

# --- BOT KOMUTLARI ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = f"Merhaba! Bot çalışıyor.\nSenin ID'n: `{user_id}`\n"
    if user_id not in ALLOWED_USERS:
        msg += "⚠️ Yetkili kullanıcı değilsin. ID'ni koda ekle."
    else:
        msg += "Komutlar:\n/add <url> <beden> - Ürün ekle (Örn: /add https://zara.com... M)\n/list - Listele\n/delete <no> - Sil"
    await update.message.reply_text(msg)

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    
    try:
        # Örn: /add https://zara... S
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Kullanım: /add <LINK> <BEDEN>\nÖrnek: /add https://zara.com/urun... M")
            return

        url = args[0]
        size = args[1].upper() # Beden (S, M, L, 36, 42 vs.)
        
        data = load_data()
        if str(update.effective_user.id) not in data:
            data[str(update.effective_user.id)] = []
            
        data[str(update.effective_user.id)].append({"url": url, "size": size, "last_status": False})
        save_data(data)
        
        await update.message.reply_text(f"✅ Takibe alındı: {size} beden.")
        
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    data = load_data()
    user_items = data.get(str(update.effective_user.id), [])
    
    if not user_items:
        await update.message.reply_text("Hiç ürün yok.")
        return
        
    msg = "📋 **Takip Listesi**\n"
    for i, item in enumerate(user_items):
        msg += f"{i+1}. {item['size']} - [Link]({item['url']})\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return
    try:
        idx = int(context.args[0]) - 1
        data = load_data()
        user_list = data.get(str(update.effective_user.id), [])
        
        if 0 <= idx < len(user_list):
            removed = user_list.pop(idx)
            save_data(data)
            await update.message.reply_text(f"🗑️ Silindi: {removed['size']}")
        else:
            await update.message.reply_text("Geçersiz numara.")
    except:
        await update.message.reply_text("Kullanım: /delete <liste_numarası>")

# --- ARKA PLAN GÖREVİ (STOCK CHECKER) ---

async def background_checker(app: Application):
    """Sürekli çalışan döngü"""
    logger.info("Stok takipçisi başlatıldı...")
    while True:
        try:
            data = load_data()
            driver = None
            
            # Eğer kontrol edilecek ürün varsa tarayıcıyı aç
            has_items = any(len(items) > 0 for items in data.values())
            
            if has_items:
                logger.info("Tarayıcı başlatılıyor...")
                driver = get_driver()
                
                for user_id, items in data.items():
                    for item in items:
                        url = item['url']
                        size = item['size']
                        
                        # Şu an sadece Zara mantığı ekli, diğerleri için if/else eklenebilir
                        if "zara" in url:
                            found_sizes = check_zara_stock(driver, url, [size])
                            
                            if size in found_sizes:
                                msg = f"🚨 **STOK BULUNDU!** 🚨\n\nMağaza: Zara\nBeden: {size}\nLink: {url}"
                                await app.bot.send_message(chat_id=user_id, text=msg)
                                logger.info(f"Stok bulundu: {url}")
                            else:
                                logger.info(f"Stok yok: {url} ({size})")
                        
                        await asyncio.sleep(5) # Siteler arası bekleme
                
                driver.quit()
                
            else:
                logger.info("Takip listesi boş.")
                
        except Exception as e:
            logger.error(f"Döngü hatası: {e}")
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        # Bekleme süresi
        await asyncio.sleep(CHECK_INTERVAL)

# --- MAIN ---

if __name__ == "__main__":
    # Uygulamayı oluştur
    application = Application.builder().token(TOKEN).build()

    # Komutları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_product))
    application.add_handler(CommandHandler("list", list_products))
    application.add_handler(CommandHandler("delete", delete_product))

    # Arka plan görevini başlat (async loop içinde)
    loop = asyncio.get_event_loop()
    loop.create_task(background_checker(application))

    # Botu çalıştır
    application.run_polling()
