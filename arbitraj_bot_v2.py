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

MIN_KAR_YUZDE = 0.5   # minimum %0.5 fark
MAX_ISLEM_ETH  = 0.003 # max işlem miktarı ETH
TARAMA_SURESI  = 10    # saniye (30'dan 10'a indirdik)
LOG_DOSYA      = "arbitraj_log.txt"

# Güvenilir coinler (Base ağı)
COINLER = {
    "WETH":  "0x4200000000000000000000000000000000000006",
    "USDC":  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "DAI":   "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
}

# ERC20 ABI (balanceOf için)
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]')

def log(mesaj):
    zaman = datetime.now().strftime("%H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYA, "a", encoding="utf-8") as f:
        f.write(satir + "\n")

def baglanti_kontrol():
    try:
        if w3.is_connected():
            blok = w3.eth.block_number
            log(f"✅ Base ağına bağlandı! Blok: #{blok}")
            return True
    except Exception as e:
        log(f"❌ Bağlantı hatası: {e}")
    return False

def bakiye_kontrol():
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        eth = w3.from_wei(w3.eth.get_balance(adres), 'ether')
        log(f"💰 ETH: {eth:.6f}")

        # USDC bakiye
        try:
            usdc = w3.eth.contract(
                address=Web3.to_checksum_address(COINLER["USDC"]),
                abi=ERC20_ABI
            )
            usdc_bal = usdc.functions.balanceOf(adres).call() / 1e6
            log(f"💵 USDC: {usdc_bal:.2f}")
        except:
            pass

        return float(eth)
    except Exception as e:
        log(f"❌ Bakiye hatası: {e}")
        return 0

# === FIYAT ALMA ===

def fiyat_uniswap_v3(token_in, token_out, miktar_usd=1):
    """Uniswap V3 Quoter kontratından fiyat al (Base ağı)"""
    try:
        # Uniswap V3 Quoter V2 (Base ağı)
        QUOTER = "0x3d4e44Eb1374240CE5F1B136aa68B6a6e4f26C84"
        QUOTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],"name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},{"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},{"internalType":"uint256","name":"gasEstimate","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]')

        quoter = w3.eth.contract(
            address=Web3.to_checksum_address(QUOTER),
            abi=QUOTER_ABI
        )

        # 1 USDC = 1e6 (6 decimal)
        if token_in == COINLER["USDC"]:
            miktar = int(miktar_usd * 1e6)
        else:
            miktar = int(miktar_usd * 1e18)

        sonuc = quoter.functions.quoteExactInputSingle({
            'tokenIn': Web3.to_checksum_address(token_in),
            'tokenOut': Web3.to_checksum_address(token_out),
            'amountIn': miktar,
            'fee': 500,  # %0.05 havuz
            'sqrtPriceLimitX96': 0
        }).call()

        return sonuc[0]
    except:
        return 0

def fiyat_aerodrome(token_in, token_out, miktar_usd=1):
    """Aerodrome'dan fiyat al (Base'in en büyük DEX'i)"""
    try:
        ROUTER = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
        ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')

        router = w3.eth.contract(
            address=Web3.to_checksum_address(ROUTER),
            abi=ABI
        )

        if token_in == COINLER["USDC"]:
            miktar = int(miktar_usd * 1e6)
        else:
            miktar = int(miktar_usd * 1e18)

        sonuc = router.functions.getAmountsOut(
            miktar,
            [Web3.to_checksum_address(token_in),
             Web3.to_checksum_address(token_out)]
        ).call()

        return sonuc[-1]
    except:
        return 0

def coingecko_fiyat(sembol):
    """Yedek: CoinGecko'dan USD fiyatı"""
    try:
        id_map = {"WETH": "ethereum", "USDC": "usd-coin", "DAI": "dai"}
        cg_id = id_map.get(sembol, "")
        if not cg_id:
            return 0
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd",
            timeout=4
        )
        return r.json().get(cg_id, {}).get("usd", 0)
    except:
        return 0

# === ARBİTRAJ TARAMA ===

def arbitraj_tara():
    """Tüm çiftleri tara, en iyi fırsatı bul"""
    en_iyi = None
    en_iyi_fark = 0

    coin_listesi = list(COINLER.items())

    for i in range(len(coin_listesi)):
        for j in range(len(coin_listesi)):
            if i == j:
                continue

            isim_a, adres_a = coin_listesi[i]
            isim_b, adres_b = coin_listesi[j]

            try:
                # Uniswap V3 fiyatı
                uni_fiyat = fiyat_uniswap_v3(adres_a, adres_b)
                # Aerodrome fiyatı
                aero_fiyat = fiyat_aerodrome(adres_a, adres_b)

                if uni_fiyat <= 0 or aero_fiyat <= 0:
                    continue

                # Fark hesapla
                fark = abs(uni_fiyat - aero_fiyat) / max(uni_fiyat, aero_fiyat) * 100

                if fark >= MIN_KAR_YUZDE:
                    ucuz = "Uniswap" if uni_fiyat < aero_fiyat else "Aerodrome"
                    pahali = "Aerodrome" if uni_fiyat < aero_fiyat else "Uniswap"
                    log(f"🔍 {isim_a}→{isim_b} | Fark: %{fark:.3f} | Al:{ucuz} Sat:{pahali}")

                    if fark > en_iyi_fark:
                        en_iyi_fark = fark
                        en_iyi = {
                            "token_a_isim": isim_a,
                            "token_b_isim": isim_b,
                            "token_a": adres_a,
                            "token_b": adres_b,
                            "fark": fark,
                            "ucuz_dex": ucuz,
                            "pahali_dex": pahali,
                            "uni_fiyat": uni_fiyat,
                            "aero_fiyat": aero_fiyat,
                        }
            except:
                continue

    return en_iyi

# === GAS ===

def gas_ucreti_eth():
    try:
        gas_fiyat = w3.eth.gas_price
        gas_limit = 250000
        return float(w3.from_wei(gas_fiyat * gas_limit, 'ether'))
    except:
        return 0.001

# === SWAP İŞLEMİ (simüle) ===

def swap_yap(firsat):
    """Arbitraj işlemini gerçekleştir"""
    try:
        gas = gas_ucreti_eth()
        bakiye = float(w3.from_wei(
            w3.eth.get_balance(Web3.to_checksum_address(CUZDAN)), 'ether'))

        log(f"⚡ Fırsat: {firsat['token_a_isim']}→{firsat['token_b_isim']}")
        log(f"   Fark: %{firsat['fark']:.3f}")
        log(f"   Al: {firsat['ucuz_dex']} | Sat: {firsat['pahali_dex']}")
        log(f"   Gas: {gas:.6f} ETH | Bakiye: {bakiye:.6f} ETH")

        if bakiye < gas * 3:
            log("❌ Yetersiz ETH! Gas için en az 3x gas gerekli.")
            return False

        # Şu an simülasyon modu
        # Gerçek swap için router kontrat çağrısı eklenecek
        log(f"📋 [SİMÜLASYON] Tahmini kar: %{firsat['fark']:.3f}")
        log("✅ Gerçek swap yakında aktif olacak!")
        return True

    except Exception as e:
        log(f"❌ Swap hatası: {e}")
        return False

# === ANA DÖNGÜ ===

def main():
    log("=" * 55)
    log("🤖 ARBİTRAJ BOTU v2 BAŞLADI")
    log("=" * 55)
    log(f"Cüzdan : {CUZDAN}")
    log(f"Min kar: %{MIN_KAR_YUZDE}")
    log(f"Tarama : {TARAMA_SURESI} saniyede bir")
    log("=" * 55)

    if not baglanti_kontrol():
        log("❌ Çıkılıyor...")
        return

    bakiye_kontrol()

    dongu = 0
    while True:
        dongu += 1
        log(f"\n🔄 Tarama #{dongu}")

        try:
            firsat = arbitraj_tara()

            if firsat:
                log(f"✅ EN İYİ FIRSAT: %{firsat['fark']:.3f}")
                swap_yap(firsat)
            else:
                log("😴 Fırsat yok, bekleniyor...")

        except KeyboardInterrupt:
            log("🛑 Bot durduruldu!")
            break
        except Exception as e:
            log(f"❌ Hata: {e}")

        time.sleep(TARAMA_SURESI)

if __name__ == "__main__":
    main()
