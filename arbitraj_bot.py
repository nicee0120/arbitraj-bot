import os
import time
import json
import requests
from web3 import Web3
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# === AYARLAR ===
ALCHEMY_URL = os.getenv("ALCHEMY_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CUZDAN = os.getenv("CUZDAN_ADRESI")

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

# Minimum kar (gas dahil) — dolar cinsinden
MIN_KAR_DOLAR = 0.3

# Maksimum işlem başına harcama (dolar)
MAX_ISLEM_DOLAR = 5.0

# Güvenilir coinler (Base ağı adresleri)
COINLER = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006",
    "DAI":  "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "WBTC": "0x1ceA84203673764244E05693e42E6Ace62bE9BA5",
}

# DEX Router adresleri (Base ağı)
DEXLER = {
    "BaseSwap": "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86",
    "Aerodrome": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
}

# Log dosyası
LOG_DOSYA = "arbitraj_log.txt"

def log(mesaj):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYA, "a") as f:
        f.write(satir + "\n")

def baglanti_kontrol():
    if w3.is_connected():
        log("✅ Base ağına bağlandı!")
        return True
    else:
        log("❌ Bağlantı hatası!")
        return False

def bakiye_kontrol():
    try:
        bakiye_wei = w3.eth.get_balance(Web3.to_checksum_address(CUZDAN))
        bakiye_eth = w3.from_wei(bakiye_wei, 'ether')
        log(f"💰 Cüzdan bakiyesi: {bakiye_eth:.6f} ETH")
        return float(bakiye_eth)
    except Exception as e:
        log(f"❌ Bakiye kontrol hatası: {e}")
        return 0

def fiyat_al_uniswap(token_in, token_out, miktar):
    """Uniswap V3 fiyat sorgula (Base ağı)"""
    try:
        url = "https://api.uniswap.org/v1/quote"
        params = {
            "tokenInAddress": token_in,
            "tokenInChainId": 8453,
            "tokenOutAddress": token_out,
            "tokenOutChainId": 8453,
            "amount": str(miktar),
            "type": "exactIn"
        }
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return float(data.get("quoteDecimals", 0))
    except:
        pass
    return 0

def fiyat_al_dex(dex_adi, token_in, token_out, miktar):
    """DEX'ten fiyat al — simüle"""
    try:
        # Gerçek fiyat için DEX router ABI gerekir
        # Şimdilik CoinGecko'dan fiyat alıyoruz
        base_fiyat = fiyat_coingecko(token_in, token_out)
        if base_fiyat > 0:
            # Her DEX'in hafif farklı fiyatı olur (slippage simülasyonu)
            import random
            sapma = random.uniform(-0.005, 0.005)  # %0.5 sapma
            return base_fiyat * (1 + sapma)
    except:
        pass
    return 0

def fiyat_coingecko(token_in_adres, token_out_adres):
    """CoinGecko'dan fiyat al"""
    try:
        adres_id = {
            "0x4200000000000000000000000000000000000006": "ethereum",
            "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913": "usd-coin",
            "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb": "dai",
            "0x1ceA84203673764244E05693e42E6Ace62bE9BA5": "wrapped-bitcoin",
        }
        id_in = adres_id.get(token_in_adres.lower(), "")
        id_out = adres_id.get(token_out_adres.lower(), "")
        if not id_in or not id_out:
            return 0
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={id_in},{id_out}&vs_currencies=usd"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            fiyat_in = data.get(id_in, {}).get("usd", 0)
            fiyat_out = data.get(id_out, {}).get("usd", 0)
            if fiyat_in > 0 and fiyat_out > 0:
                return fiyat_in / fiyat_out
    except:
        pass
    return 0

def arbitraj_firsati_bul():
    """Tüm coin çiftlerinde arbitraj fırsatı ara"""
    coin_listesi = list(COINLER.items())
    fırsatlar = []

    for i in range(len(coin_listesi)):
        for j in range(len(coin_listesi)):
            if i == j:
                continue

            isim_a, adres_a = coin_listesi[i]
            isim_b, adres_b = coin_listesi[j]

            try:
                # DEX 1 fiyatı
                fiyat1 = fiyat_al_dex("BaseSwap", adres_a, adres_b, 1)
                # DEX 2 fiyatı
                fiyat2 = fiyat_al_dex("Aerodrome", adres_a, adres_b, 1)

                if fiyat1 <= 0 or fiyat2 <= 0:
                    continue

                # Fiyat farkı
                fark = abs(fiyat1 - fiyat2) / max(fiyat1, fiyat2) * 100

                if fark > 0.5:  # %0.5'ten fazla fark varsa
                    ucuz_dex = "BaseSwap" if fiyat1 < fiyat2 else "Aerodrome"
                    pahali_dex = "Aerodrome" if fiyat1 < fiyat2 else "BaseSwap"
                    log(f"🔍 Fırsat: {isim_a}→{isim_b} | Fark: %{fark:.2f} | Al: {ucuz_dex} | Sat: {pahali_dex}")
                    fırsatlar.append({
                        "token_a": isim_a,
                        "token_b": isim_b,
                        "adres_a": adres_a,
                        "adres_b": adres_b,
                        "fark": fark,
                        "ucuz_dex": ucuz_dex,
                        "pahali_dex": pahali_dex
                    })

            except Exception as e:
                pass

    # En iyi fırsatı seç
    if fırsatlar:
        en_iyi = max(fırsatlar, key=lambda x: x["fark"])
        return en_iyi
    return None

def gas_hesapla():
    """Gas ücretini ETH cinsinden hesapla"""
    try:
        gas_fiyat = w3.eth.gas_price
        gas_limit = 300000  # arbitraj için tahmini
        gas_eth = w3.from_wei(gas_fiyat * gas_limit, 'ether')
        return float(gas_eth)
    except:
        return 0.001  # varsayılan

def islem_yap(firsat):
    """Arbitraj işlemini gerçekleştir"""
    try:
        log(f"⚡ İşlem yapılıyor: {firsat['token_a']} → {firsat['token_b']}")
        log(f"   Al: {firsat['ucuz_dex']} | Sat: {firsat['pahali_dex']}")

        # Gas hesapla
        gas = gas_hesapla()
        log(f"   Gas ücreti: {gas:.6f} ETH")

        # Bakiye kontrol
        bakiye = bakiye_kontrol()
        if bakiye < gas * 2:
            log("❌ Yetersiz bakiye! İşlem iptal.")
            return False

        # Gerçek işlem için DEX router ABI ve swap fonksiyonu gerekir
        # Bu kısım ilerleyen adımda eklenecek
        log("📋 İşlem simüle edildi (gerçek swap yakında eklenecek)")
        log(f"✅ Tahmini kar: %{firsat['fark']:.2f}")
        return True

    except Exception as e:
        log(f"❌ İşlem hatası: {e}")
        return False

def main():
    log("=" * 50)
    log("🤖 ARBİTRAJ BOTU BAŞLADI")
    log("=" * 50)
    log(f"Cüzdan: {CUZDAN}")
    log(f"Min kar: ${MIN_KAR_DOLAR}")
    log(f"Max işlem: ${MAX_ISLEM_DOLAR}")
    log("=" * 50)

    if not baglanti_kontrol():
        log("❌ Bağlantı kurulamadı, çıkılıyor...")
        return

    bakiye_kontrol()

    dongu = 0
    while True:
        dongu += 1
        log(f"\n🔄 Tarama #{dongu}")

        try:
            firsat = arbitraj_firsati_bul()

            if firsat:
                log(f"✅ Fırsat bulundu! Fark: %{firsat['fark']:.2f}")
                islem_yap(firsat)
            else:
                log("😴 Fırsat bulunamadı, bekleniyor...")

        except Exception as e:
            log(f"❌ Hata: {e}")

        # 30 saniye bekle
        log("⏳ 30 saniye bekleniyor...")
        time.sleep(30)

if __name__ == "__main__":
    main()
