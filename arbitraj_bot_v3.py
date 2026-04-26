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
PRIVATE_KEY  = os.getenv("PRIVATE_KEY")
CUZDAN       = os.getenv("CUZDAN_ADRESI")

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

MIN_KAR_YUZDE  = 0.8    # minimum %0.8 fark (gas dahil karlı olsun)
ISLEM_USDC     = 5.0    # her işlemde kullan (dolar)
TARAMA_SURESI  = 8      # saniye
LOG_DOSYA      = "arbitraj_log.txt"
GUNLUK_LIMIT   = 2.0    # günlük max kayıp (dolar)

# === TOKEN ADRESLERİ (Base ağı) ===
WETH  = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC  = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
DAI   = Web3.to_checksum_address("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb")

COINLER = {"WETH": WETH, "USDC": USDC, "DAI": DAI}

# === UNISWAP V3 (Base ağı) ===
UNISWAP_ROUTER   = Web3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")
UNISWAP_QUOTER   = Web3.to_checksum_address("0x3d4e44Eb1374240CE5F1B136aa68B6a6e4f26C84")

# === AERODROME (Base ağı) ===
AERODROME_ROUTER = Web3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")

# === ABI'ler ===
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

UNISWAP_ROUTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMinimum","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IV3SwapRouter.ExactInputSingleParams","name":"params","type":"tuple"}],"name":"exactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],"stateMutability":"payable","type":"function"}]')

QUOTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],"name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},{"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},{"internalType":"uint256","name":"gasEstimate","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]')

AERODROME_ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')

AERODROME_FACTORY = Web3.to_checksum_address("0x420DD381b31aEf6683db6B902084cB0FFECe40Da")

# === YARDIMCI ===
gunluk_kayip = 0.0

def log(mesaj):
    zaman = datetime.now().strftime("%H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYA, "a", encoding="utf-8") as f:
        f.write(satir + "\n")

def decimals(token_adres):
    return 6 if token_adres == USDC else 18

def miktar_to_wei(miktar, token):
    return int(miktar * (10 ** decimals(token)))

def wei_to_miktar(wei, token):
    return wei / (10 ** decimals(token))

# === BAKİYE ===
def bakiye_goster():
    adres = Web3.to_checksum_address(CUZDAN)
    eth = float(w3.from_wei(w3.eth.get_balance(adres), 'ether'))
    log(f"💰 ETH: {eth:.6f}")
    for isim, token in COINLER.items():
        if token == WETH:
            continue
        try:
            kontrat = w3.eth.contract(address=token, abi=ERC20_ABI)
            bal = kontrat.functions.balanceOf(adres).call()
            log(f"💵 {isim}: {wei_to_miktar(bal, token):.4f}")
        except:
            pass
    return eth

# === FİYAT ALMA ===
def uniswap_fiyat(token_in, token_out, miktar):
    try:
        id_map = {
            WETH: "ethereum",
            USDC: "usd-coin",
            DAI: "dai"
        }
        id_in  = id_map.get(token_in, "")
        id_out = id_map.get(token_out, "")
        if not id_in or not id_out:
            return 0
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={id_in},{id_out}&vs_currencies=usd",
            timeout=5
        )
        data = r.json()
        fiyat_in  = data.get(id_in,  {}).get("usd", 0)
        fiyat_out = data.get(id_out, {}).get("usd", 0)
        if fiyat_in > 0 and fiyat_out > 0:
            oran = fiyat_in / fiyat_out
            return int(miktar * oran * 0.997)
        return 0
    except:
        return 0

def aerodrome_fiyat(token_in, token_out, miktar):
    try:
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        sonuc = router.functions.getAmountsOut(
            miktar,
            [{"from": token_in, "to": token_out,
              "stable": False, "factory": AERODROME_FACTORY}]
        ).call()
        return sonuc[-1]
    except:
        try:
            router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
            sonuc = router.functions.getAmountsOut(
                miktar,
                [{"from": token_in, "to": token_out,
                  "stable": True, "factory": AERODROME_FACTORY}]
            ).call()
            return sonuc[-1]
        except:
            return 0

# === APPROVE ===
def approve(token, spender, miktar):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        kontrat = w3.eth.contract(address=token, abi=ERC20_ABI)

        # Mevcut allowance kontrol
        mevcut = kontrat.functions.allowance(adres, spender).call()
        if mevcut >= miktar:
            return True

        nonce = w3.eth.get_transaction_count(adres)
        tx = kontrat.functions.approve(spender, miktar * 10).build_transaction({
            'from': adres,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': 8453
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"✅ Approve tx: {tx_hash.hex()[:20]}...")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        return True
    except Exception as e:
        log(f"❌ Approve hatası: {e}")
        return False

# === UNISWAP SWAP ===
def uniswap_swap(token_in, token_out, miktar_in, min_out, fee=500):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=UNISWAP_ROUTER, abi=UNISWAP_ROUTER_ABI)
        nonce = w3.eth.get_transaction_count(adres)
        deadline = int(time.time()) + 300

        tx = router.functions.exactInputSingle({
            'tokenIn': token_in,
            'tokenOut': token_out,
            'fee': fee,
            'recipient': adres,
            'amountIn': miktar_in,
            'amountOutMinimum': int(min_out * 0.99),  # %1 slippage
            'sqrtPriceLimitX96': 0
        }).build_transaction({
            'from': adres,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': 8453,
            'value': 0
        })

        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Uniswap tx: {tx_hash.hex()[:20]}...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            log("✅ Uniswap swap başarılı!")
            return True
        else:
            log("❌ Uniswap swap başarısız!")
            return False
    except Exception as e:
        log(f"❌ Uniswap swap hatası: {e}")
        return False

# === AERODROME SWAP ===
def aerodrome_swap(token_in, token_out, miktar_in, min_out, stable=False):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        nonce = w3.eth.get_transaction_count(adres)
        deadline = int(time.time()) + 300

        tx = router.functions.swapExactTokensForTokens(
            miktar_in,
            int(min_out * 0.99),
            [{"from": token_in, "to": token_out,
              "stable": stable, "factory": AERODROME_FACTORY}],
            adres,
            deadline
        ).build_transaction({
            'from': adres,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': 8453,
            'value': 0
        })

        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Aerodrome tx: {tx_hash.hex()[:20]}...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            log("✅ Aerodrome swap başarılı!")
            return True
        else:
            log("❌ Aerodrome swap başarısız!")
            return False
    except Exception as e:
        log(f"❌ Aerodrome swap hatası: {e}")
        return False

# === ARBİTRAJ TARA ===
def arbitraj_tara():
    en_iyi = None
    en_iyi_fark = 0

    # USDC → WETH → USDC arası fırsat ara
    ciftler = [
        ("USDC", USDC, "WETH", WETH),
        ("WETH", WETH, "USDC", USDC),
    ]

    islem_miktari = miktar_to_wei(ISLEM_USDC, USDC)

    for isim_a, adres_a, isim_b, adres_b in ciftler:
        try:
            if adres_a == USDC:
                miktar = islem_miktari
            else:
                # ETH bakiyesinin yarısını kullan
                adres = Web3.to_checksum_address(CUZDAN)
                eth_bal = w3.eth.get_balance(adres)
                miktar = eth_bal // 4  # çeyreği

            if miktar <= 0:
                continue

            uni  = uniswap_fiyat(adres_a, adres_b, miktar)
            aero = aerodrome_fiyat(adres_a, adres_b, miktar)

            if uni <= 0 or aero <= 0:
                log(f"⚠️  {isim_a}→{isim_b}: Fiyat alınamadı")
                continue

            fark = abs(uni - aero) / max(uni, aero) * 100

            log(f"📊 {isim_a}→{isim_b} | Uni:{uni} Aero:{aero} | Fark:%{fark:.3f}")

            if fark >= MIN_KAR_YUZDE and fark > en_iyi_fark:
                en_iyi_fark = fark
                ucuz  = "Uniswap"  if uni > aero else "Aerodrome"
                pahali = "Aerodrome" if uni > aero else "Uniswap"
                en_iyi = {
                    "token_a_isim": isim_a,
                    "token_b_isim": isim_b,
                    "token_a": adres_a,
                    "token_b": adres_b,
                    "miktar": miktar,
                    "uni_out": uni,
                    "aero_out": aero,
                    "fark": fark,
                    "ucuz_dex": ucuz,
                    "pahali_dex": pahali,
                }
        except Exception as e:
            log(f"⚠️  Tarama hatası {isim_a}→{isim_b}: {e}")

    return en_iyi

# === GERÇEK ARBİTRAJ ===
def arbitraj_yap(f):
    global gunluk_kayip

    log(f"🚀 ARBİTRAJ BAŞLIYOR!")
    log(f"   {f['token_a_isim']} → {f['token_b_isim']}")
    log(f"   Al: {f['ucuz_dex']} | Sat: {f['pahali_dex']}")
    log(f"   Fark: %{f['fark']:.3f}")

    token_a = f['token_a']
    token_b = f['token_b']
    miktar  = f['miktar']

    # Adım 1: Approve
    if f['ucuz_dex'] == "Uniswap":
        if not approve(token_a, UNISWAP_ROUTER, miktar):
            return False
    else:
        if not approve(token_a, AERODROME_ROUTER, miktar):
            return False

    # Adım 2: İlk swap (ucuz DEX'ten al)
    if f['ucuz_dex'] == "Uniswap":
        basari = uniswap_swap(token_a, token_b, miktar, f['uni_out'])
        ara_miktar = f['uni_out']
    else:
        basari = aerodrome_swap(token_a, token_b, miktar, f['aero_out'])
        ara_miktar = f['aero_out']

    if not basari:
        log("❌ İlk swap başarısız! Durduruluyor.")
        return False

    log(f"✅ 1. swap tamamlandı! {wei_to_miktar(ara_miktar, token_b):.6f} {f['token_b_isim']} alındı")

    time.sleep(2)

    # Adım 3: Approve (pahalı DEX için)
    if f['pahali_dex'] == "Uniswap":
        if not approve(token_b, UNISWAP_ROUTER, ara_miktar):
            return False
    else:
        if not approve(token_b, AERODROME_ROUTER, ara_miktar):
            return False

    # Adım 4: İkinci swap (pahalı DEX'te sat)
    if f['pahali_dex'] == "Uniswap":
        basari2 = uniswap_swap(token_b, token_a, ara_miktar, miktar)
    else:
        basari2 = aerodrome_swap(token_b, token_a, ara_miktar, miktar)

    if basari2:
        log(f"🎉 ARBİTRAJ TAMAMLANDI! Tahmini kar: %{f['fark']:.3f}")
    else:
        log("❌ 2. swap başarısız!")

    return basari2

# === ANA DÖNGÜ ===
def main():
    log("=" * 55)
    log("🤖 ARBİTRAJ BOTU v3 — GERÇEK SWAP")
    log("=" * 55)
    log(f"Cüzdan : {CUZDAN}")
    log(f"Min kar: %{MIN_KAR_YUZDE}")
    log(f"İşlem  : ${ISLEM_USDC} USDC")
    log(f"Tarama : {TARAMA_SURESI}s")
    log("=" * 55)

    if not w3.is_connected():
        log("❌ Bağlantı yok!")
        return

    blok = w3.eth.block_number
    log(f"✅ Bağlandı! Blok: #{blok}")
    bakiye_goster()

    dongu = 0
    while True:
        dongu += 1
        log(f"\n🔄 Tarama #{dongu}")

        try:
            firsat = arbitraj_tara()

            if firsat:
                log(f"✅ FIRSAT BULUNDU! %{firsat['fark']:.3f}")
                arbitraj_yap(firsat)
                bakiye_goster()
            else:
                log("😴 Fırsat yok...")

        except KeyboardInterrupt:
            log("🛑 Bot durduruldu!")
            break
        except Exception as e:
            log(f"❌ Hata: {e}")

        time.sleep(TARAMA_SURESI)

if __name__ == "__main__":
    main()

python3 -c "
from web3 import Web3
from dotenv import load_dotenv
import os, time
load_dotenv()
w3 = Web3(Web3.HTTPProvider(os.getenv('ALCHEMY_URL')))
print('WETH bakiye kontrol ediliyor...')
WETH = w3.eth.contract(
    address=Web3.to_checksum_address('0x4200000000000000000000000000000000000006'),
    abi=[{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'}]
)
bal = WETH.functions.balanceOf(Web3.to_checksum_address(os.getenv('CUZDAN_ADRESI'))).call()
print(f'WETH: {bal/1e18:.6f}')
"
