import os
import time
import json
import requests
from web3 import Web3
from dotenv import load_dotenv
from datetime import datetime
from itertools import combinations

load_dotenv()

ALCHEMY_URL = os.getenv("ALCHEMY_URL")
PRIVATE_KEY  = os.getenv("PRIVATE_KEY")
CUZDAN       = os.getenv("CUZDAN_ADRESI")

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

MIN_KAR_YUZDE = 0.5
ISLEM_USDC    = 4.0
TARAMA_SURESI = 8
LOG_DOSYA     = "arbitraj_log.txt"

# === TOKEN ADRESLERİ (Base ağı) ===
TOKENS = {
    "USDC": Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
    "WETH": Web3.to_checksum_address("0x4200000000000000000000000000000000000006"),
    "DAI":  Web3.to_checksum_address("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb"),
    "WBTC": Web3.to_checksum_address("0x1ceA84203673764244E05693e42E6Ace62bE9BA5"),
    "cbETH":Web3.to_checksum_address("0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22"),
}

DECIMALS = {
    "USDC": 6,
    "WETH": 18,
    "DAI":  18,
    "WBTC": 8,
    "cbETH":18,
}

# === DEX ADRESLERİ (Base ağı) ===
UNISWAP_QUOTER   = Web3.to_checksum_address("0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a")
UNISWAP_ROUTER   = Web3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")

AERODROME_ROUTER  = Web3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")
AERODROME_FACTORY = Web3.to_checksum_address("0x420DD381b31aEf6683db6B902084cB0FFECe40Da")

BASESWAP_ROUTER  = Web3.to_checksum_address("0x327Df1E6de05895d2ab08513aaDD9313Fe505d86")
SUSHI_ROUTER     = Web3.to_checksum_address("0x6BDED42c6DA8FBf0d2bA55B2fa120C5e0c8D7891")

# === ABI'ler ===
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

QUOTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],"name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},{"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},{"internalType":"uint256","name":"gasEstimate","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]')

UNISWAP_ROUTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMinimum","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IV3SwapRouter.ExactInputSingleParams","name":"params","type":"tuple"}],"name":"exactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],"stateMutability":"payable","type":"function"}]')

AERODROME_ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')

V2_ROUTER_ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]')

# === YARDIMCI ===
def log(mesaj):
    zaman = datetime.now().strftime("%H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYA, "a", encoding="utf-8") as f:
        f.write(satir + "\n")

def dec(token_isim):
    return DECIMALS.get(token_isim, 18)

def bakiye_goster():
    adres = Web3.to_checksum_address(CUZDAN)
    eth = float(w3.from_wei(w3.eth.get_balance(adres), 'ether'))
    log(f"💰 ETH:{eth:.5f}")
    for isim, adres_t in TOKENS.items():
        try:
            k = w3.eth.contract(address=adres_t, abi=ERC20_ABI)
            b = k.functions.balanceOf(Web3.to_checksum_address(CUZDAN)).call()
            amount = b / (10 ** dec(isim))
            if amount > 0.0001:
                log(f"   {isim}: {amount:.4f}")
        except:
            pass
    return eth

# === FİYAT ALMA ===
def uniswap_quote(token_in_adres, token_out_adres, miktar, fee=500):
    try:
        quoter = w3.eth.contract(address=UNISWAP_QUOTER, abi=QUOTER_ABI)
        sonuc = quoter.functions.quoteExactInputSingle({
            "tokenIn": token_in_adres,
            "tokenOut": token_out_adres,
            "amountIn": miktar,
            "fee": fee,
            "sqrtPriceLimitX96": 0
        }).call()
        return sonuc[0]
    except:
        try:
            quoter = w3.eth.contract(address=UNISWAP_QUOTER, abi=QUOTER_ABI)
            sonuc = quoter.functions.quoteExactInputSingle({
                "tokenIn": token_in_adres,
                "tokenOut": token_out_adres,
                "amountIn": miktar,
                "fee": 3000,
                "sqrtPriceLimitX96": 0
            }).call()
            return sonuc[0]
        except:
            return 0

def aerodrome_quote(token_in_adres, token_out_adres, miktar):
    try:
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        sonuc = router.functions.getAmountsOut(
            miktar,
            [{"from": token_in_adres, "to": token_out_adres,
              "stable": False, "factory": AERODROME_FACTORY}]
        ).call()
        return sonuc[-1]
    except:
        try:
            router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
            sonuc = router.functions.getAmountsOut(
                miktar,
                [{"from": token_in_adres, "to": token_out_adres,
                  "stable": True, "factory": AERODROME_FACTORY}]
            ).call()
            return sonuc[-1]
        except:
            return 0

def baseswap_quote(token_in_adres, token_out_adres, miktar):
    try:
        router = w3.eth.contract(address=BASESWAP_ROUTER, abi=V2_ROUTER_ABI)
        sonuc = router.functions.getAmountsOut(
            miktar, [token_in_adres, token_out_adres]
        ).call()
        return sonuc[-1]
    except:
        return 0

def sushi_quote(token_in_adres, token_out_adres, miktar):
    try:
        router = w3.eth.contract(address=SUSHI_ROUTER, abi=V2_ROUTER_ABI)
        sonuc = router.functions.getAmountsOut(
            miktar, [token_in_adres, token_out_adres]
        ).call()
        return sonuc[-1]
    except:
        return 0

def tum_dex_quote(token_in_adres, token_out_adres, miktar):
    """Tüm DEX'lerden fiyat al"""
    fiyatlar = {}
    u = uniswap_quote(token_in_adres, token_out_adres, miktar)
    if u > 0: fiyatlar["Uniswap"] = u
    a = aerodrome_quote(token_in_adres, token_out_adres, miktar)
    if a > 0: fiyatlar["Aerodrome"] = a
    b = baseswap_quote(token_in_adres, token_out_adres, miktar)
    if b > 0: fiyatlar["BaseSwap"] = b
    s = sushi_quote(token_in_adres, token_out_adres, miktar)
    if s > 0: fiyatlar["Sushi"] = s
    return fiyatlar

# === APPROVE ===
def approve_token(token_adres, spender, miktar):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        k = w3.eth.contract(address=token_adres, abi=ERC20_ABI)
        if k.functions.allowance(adres, spender).call() >= miktar:
            return True
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = k.functions.approve(spender, 2**256-1).build_transaction({
            'from': adres, 'gas': 100000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce, 'chainId': 8453
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📋 Approve: {tx_hash.hex()[:14]}...")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        time.sleep(2)
        return True
    except Exception as e:
        log(f"❌ Approve hata: {e}")
        return False

# === SWAP FONKSİYONLARI ===
def uniswap_swap(token_in, token_out, miktar_in, min_out):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=UNISWAP_ROUTER, abi=UNISWAP_ROUTER_ABI)
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = router.functions.exactInputSingle({
            'tokenIn': token_in, 'tokenOut': token_out,
            'fee': 500, 'recipient': adres,
            'amountIn': miktar_in,
            'amountOutMinimum': int(min_out * 0.98),
            'sqrtPriceLimitX96': 0
        }).build_transaction({
            'from': adres, 'gas': 350000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce, 'chainId': 8453, 'value': 0
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Uniswap: {tx_hash.hex()[:14]}...")
        r = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return r['status'] == 1
    except Exception as e:
        log(f"❌ Uniswap swap: {e}")
        return False

def aerodrome_swap(token_in, token_out, miktar_in, min_out, stable=False):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = router.functions.swapExactTokensForTokens(
            miktar_in, int(min_out * 0.98),
            [{"from": token_in, "to": token_out,
              "stable": stable, "factory": AERODROME_FACTORY}],
            adres, int(time.time()) + 300
        ).build_transaction({
            'from': adres, 'gas': 350000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce, 'chainId': 8453, 'value': 0
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Aerodrome: {tx_hash.hex()[:14]}...")
        r = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return r['status'] == 1
    except Exception as e:
        log(f"❌ Aerodrome swap: {e}")
        return False

def v2_swap(router_adres, token_in, token_out, miktar_in, min_out):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=router_adres, abi=V2_ROUTER_ABI)
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = router.functions.swapExactTokensForTokens(
            miktar_in, int(min_out * 0.98),
            [token_in, token_out],
            adres, int(time.time()) + 300
        ).build_transaction({
            'from': adres, 'gas': 300000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce, 'chainId': 8453, 'value': 0
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 V2 swap: {tx_hash.hex()[:14]}...")
        r = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return r['status'] == 1
    except Exception as e:
        log(f"❌ V2 swap: {e}")
        return False

def swap_yap(dex, token_in, token_out, miktar_in, min_out):
    if dex == "Uniswap":
        return uniswap_swap(token_in, token_out, miktar_in, min_out)
    elif dex == "Aerodrome":
        return aerodrome_swap(token_in, token_out, miktar_in, min_out)
    elif dex == "BaseSwap":
        return v2_swap(BASESWAP_ROUTER, token_in, token_out, miktar_in, min_out)
    elif dex == "Sushi":
        return v2_swap(SUSHI_ROUTER, token_in, token_out, miktar_in, min_out)
    return False

def router_adres(dex):
    return {
        "Uniswap": UNISWAP_ROUTER,
        "Aerodrome": AERODROME_ROUTER,
        "BaseSwap": BASESWAP_ROUTER,
        "Sushi": SUSHI_ROUTER,
    }.get(dex, UNISWAP_ROUTER)

# === ARBİTRAJ TARAMA ===
# Coin çiftleri
CIFTLER = [
    ("USDC", "WETH"),
]
def arbitraj_tara():
    en_iyi = None
    en_iyi_fark = 0

    for isim_a, isim_b in CIFTLER:
        adres_a = TOKENS[isim_a]
        adres_b = TOKENS[isim_b]

        # İşlem miktarı
        miktar = int(ISLEM_USDC * (10 ** dec(isim_a)))

        try:
            fiyatlar = tum_dex_quote(adres_a, adres_b, miktar)

            if len(fiyatlar) < 2:
                continue

            en_ucuz_dex = min(fiyatlar, key=fiyatlar.get)
            en_pahali_dex = max(fiyatlar, key=fiyatlar.get)

            ucuz_fiyat  = fiyatlar[en_ucuz_dex]
            pahali_fiyat = fiyatlar[en_pahali_dex]

            fark = (pahali_fiyat - ucuz_fiyat) / ucuz_fiyat * 100

            log(f"📊 {isim_a}→{isim_b} | " +
                " | ".join([f"{d}:{v/(10**dec(isim_b)):.6f}" for d, v in fiyatlar.items()]) +
                f" | Fark:%{fark:.3f}")

            if fark > 50: continue
            if fark >= MIN_KAR_YUZDE and fark > en_iyi_fark:
                en_iyi_fark = fark
                en_iyi = {
                    "isim_a": isim_a,
                    "isim_b": isim_b,
                    "adres_a": adres_a,
                    "adres_b": adres_b,
                    "miktar_a": miktar,
                    "al_dex": en_pahali_dex,   # en çok veren DEX'ten al
                    "sat_dex": en_ucuz_dex,    # en az veren DEX'te sat (ters işlem)
                    "beklenen_b": pahali_fiyat,
                    "fark": fark,
                    "tum_fiyatlar": fiyatlar
                }
        except Exception as e:
            log(f"⚠️  {isim_a}→{isim_b}: {e}")

    return en_iyi

def arbitraj_yap(f):
    log(f"🚀 ARBİTRAJ! {f['isim_a']}→{f['isim_b']} | Al:{f['al_dex']} Sat:{f['sat_dex']} | Fark:%{f['fark']:.3f}")

    # Adım 1: Approve + İlk swap
    if not approve_token(f['adres_a'], router_adres(f['al_dex']), f['miktar_a']):
        return False

    basari = swap_yap(f['al_dex'], f['adres_a'], f['adres_b'], f['miktar_a'], f['beklenen_b'])

    if not basari:
        log("❌ 1. swap başarısız!")
        return False

    time.sleep(3)

    # Token B bakiyesini ölç
    adres = Web3.to_checksum_address(CUZDAN)
    k = w3.eth.contract(address=f['adres_b'], abi=ERC20_ABI)
    b_bal = k.functions.balanceOf(adres).call()
    log(f"✅ {f['isim_b']} alındı: {b_bal/(10**dec(f['isim_b'])):.6f}")

    if b_bal == 0:
        log("❌ Token yok!")
        return False

    # Adım 2: Ters swap
    min_a = int(f['miktar_a'] * 0.99)
    if not approve_token(f['adres_b'], router_adres(f['sat_dex']), b_bal):
        return False

    basari2 = swap_yap(f['sat_dex'], f['adres_b'], f['adres_a'], b_bal, min_a)

    if basari2:
        log("🎉 ARBİTRAJ TAMAMLANDI!")
    else:
        log("❌ 2. swap başarısız!")

    return basari2

# === ANA DÖNGÜ ===
def main():
    log("=" * 60)
    log("🤖 ARBİTRAJ BOTU v6 — ÇOKLU DEX + ÇİFT")
    log("=" * 60)
    log(f"Cüzdan : {CUZDAN}")
    log(f"Min kar: %{MIN_KAR_YUZDE}")
    log(f"İşlem  : ${ISLEM_USDC}")
    log(f"Tarama : {TARAMA_SURESI}s")
    log(f"DEX'ler: Uniswap, Aerodrome, BaseSwap, SushiSwap")
    log(f"Çiftler: {', '.join([f'{a}/{b}' for a,b in CIFTLER])}")
    log("=" * 60)

    if not w3.is_connected():
        log("❌ Bağlantı yok!")
        return

    log(f"✅ Bağlandı! Blok: #{w3.eth.block_number}")
    bakiye_goster()

    dongu = 0
    while True:
        dongu += 1
        log(f"\n{'='*30} Tarama #{dongu} {'='*30}")
        try:
            firsat = arbitraj_tara()
            if firsat:
                log(f"\n✅ EN İYİ FIRSAT: {firsat['isim_a']}→{firsat['isim_b']} %{firsat['fark']:.3f}")
                arbitraj_yap(firsat)
                bakiye_goster()
            else:
                log("😴 Fırsat yok, bekleniyor...")
        except KeyboardInterrupt:
            log("🛑 Durduruldu!")
            break
        except Exception as e:
            log(f"❌ Hata: {e}")
        time.sleep(TARAMA_SURESI)

if __name__ == "__main__":
    main()
