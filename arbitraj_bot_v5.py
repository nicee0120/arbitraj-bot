import os
import time
import json
import requests
from web3 import Web3
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

ALCHEMY_URL = os.getenv("ALCHEMY_URL")
PRIVATE_KEY  = os.getenv("PRIVATE_KEY")
CUZDAN       = os.getenv("CUZDAN_ADRESI")
ZEROX_KEY    = os.getenv("ZEROX_API_KEY", "1faef03b-2bce-4109-a4aa-1d46255d8b1e")  # buraya kendi key'ini yaz

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

MIN_KAR_YUZDE = 0.5
ISLEM_USDC    = 4.0
TARAMA_SURESI = 10
LOG_DOSYA     = "arbitraj_log.txt"

WETH = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

UNISWAP_ROUTER    = Web3.to_checksum_address("0x2626664c2603336E57B271c5C0b26F421741e481")
AERODROME_ROUTER  = Web3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")
AERODROME_FACTORY = Web3.to_checksum_address("0x420DD381b31aEf6683db6B902084cB0FFECe40Da")

ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

UNISWAP_ROUTER_ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMinimum","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IV3SwapRouter.ExactInputSingleParams","name":"params","type":"tuple"}],"name":"exactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],"stateMutability":"payable","type":"function"}]')

AERODROME_ABI = json.loads('[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"components":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bool","name":"stable","type":"bool"},{"internalType":"address","name":"factory","type":"address"}],"internalType":"struct IRouter.Route[]","name":"routes","type":"tuple[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}]')

def log(mesaj):
    zaman = datetime.now().strftime("%H:%M:%S")
    satir = f"[{zaman}] {mesaj}"
    print(satir)
    with open(LOG_DOSYA, "a", encoding="utf-8") as f:
        f.write(satir + "\n")

def bakiye_goster():
    adres = Web3.to_checksum_address(CUZDAN)
    eth = float(w3.from_wei(w3.eth.get_balance(adres), 'ether'))
    usdc_k = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    usdc_b = usdc_k.functions.balanceOf(adres).call() / 1e6
    weth_k = w3.eth.contract(address=WETH, abi=ERC20_ABI)
    weth_b = weth_k.functions.balanceOf(adres).call() / 1e18
    log(f"💰 ETH:{eth:.5f} | USDC:{usdc_b:.2f} | WETH:{weth_b:.5f}")
    return eth, usdc_b, weth_b

def zerox_quote(miktar):
    """Uniswap V3 QuoterV2 kontratından fiyat al"""
    try:
        QUOTER = Web3.to_checksum_address("0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a")
        ABI = json.loads('[{"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],"name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},{"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},{"internalType":"uint256","name":"gasEstimate","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]')
        quoter = w3.eth.contract(address=QUOTER, abi=ABI)
        sonuc = quoter.functions.quoteExactInputSingle({
            "tokenIn": USDC,
            "tokenOut": WETH,
            "amountIn": miktar,
            "fee": 500,
            "sqrtPriceLimitX96": 0
        }).call()
        return sonuc[0]
    except Exception as e:
        log(f"⚠️  Uniswap quote hata: {e}")
        return 0

def aerodrome_quote(miktar):
    """Aerodrome'dan fiyat al"""
    try:
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        sonuc = router.functions.getAmountsOut(
            miktar,
            [{"from": USDC, "to": WETH, "stable": False, "factory": AERODROME_FACTORY}]
        ).call()
        return sonuc[-1]
    except Exception as e:
        log(f"⚠️  Aerodrome hata: {e}")
    return 0

def approve_token(token, spender, miktar):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        kontrat = w3.eth.contract(address=token, abi=ERC20_ABI)
        mevcut = kontrat.functions.allowance(adres, spender).call()
        if mevcut >= miktar:
            log("✅ Approve zaten var")
            return True
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = kontrat.functions.approve(spender, 2**256 - 1).build_transaction({
            'from': adres,
            'gas': 100000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce,
            'chainId': 8453
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📋 Approve: {tx_hash.hex()[:16]}...")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        time.sleep(2)
        return True
    except Exception as e:
        log(f"❌ Approve hatası: {e}")
        return False

def uniswap_swap(token_in, token_out, miktar_in, min_out):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=UNISWAP_ROUTER, abi=UNISWAP_ROUTER_ABI)
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = router.functions.exactInputSingle({
            'tokenIn': token_in,
            'tokenOut': token_out,
            'fee': 500,
            'recipient': adres,
            'amountIn': miktar_in,
            'amountOutMinimum': int(min_out * 0.98),
            'sqrtPriceLimitX96': 0
        }).build_transaction({
            'from': adres,
            'gas': 350000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce,
            'chainId': 8453,
            'value': 0
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Uniswap tx: {tx_hash.hex()[:16]}...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            log("✅ Uniswap swap OK!")
            return True
        log("❌ Uniswap swap FAILED!")
        return False
    except Exception as e:
        log(f"❌ Uniswap hata: {e}")
        return False

def aerodrome_swap(token_in, token_out, miktar_in, min_out, stable=False):
    try:
        adres = Web3.to_checksum_address(CUZDAN)
        router = w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ABI)
        nonce = w3.eth.get_transaction_count(adres, 'pending')
        tx = router.functions.swapExactTokensForTokens(
            miktar_in,
            int(min_out * 0.98),
            [{"from": token_in, "to": token_out, "stable": stable, "factory": AERODROME_FACTORY}],
            adres,
            int(time.time()) + 300
        ).build_transaction({
            'from': adres,
            'gas': 350000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce,
            'chainId': 8453,
            'value': 0
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log(f"📤 Aerodrome tx: {tx_hash.hex()[:16]}...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            log("✅ Aerodrome swap OK!")
            return True
        log("❌ Aerodrome swap FAILED!")
        return False
    except Exception as e:
        log(f"❌ Aerodrome hata: {e}")
        return False

def arbitraj_tara():
    miktar_usdc = int(ISLEM_USDC * 1e6)

    uni_weth  = zerox_quote(miktar_usdc)
    aero_weth = aerodrome_quote(miktar_usdc)

    log(f"📊 USDC→WETH | 0x:{uni_weth/1e18:.6f} Aero:{aero_weth/1e18:.6f}")

    if uni_weth <= 0 or aero_weth <= 0:
        log("⚠️  Fiyat alınamadı")
        return None

    fark = abs(uni_weth - aero_weth) / max(uni_weth, aero_weth) * 100
    log(f"📈 Fark: %{fark:.3f}")

    if fark < MIN_KAR_YUZDE:
        return None

    if uni_weth > aero_weth:
        return {
            "yon": "0x→AERO",
            "adim1_dex": "uniswap",
            "adim2_dex": "aerodrome",
            "miktar_a": miktar_usdc,
            "beklenen_b": uni_weth,
            "fark": fark
        }
    else:
        return {
            "yon": "AERO→0x",
            "adim1_dex": "aerodrome",
            "adim2_dex": "uniswap",
            "miktar_a": miktar_usdc,
            "beklenen_b": aero_weth,
            "fark": fark
        }

def arbitraj_yap(f):
    log(f"🚀 ARBİTRAJ! Yön:{f['yon']} Fark:%{f['fark']:.3f}")

    if f['adim1_dex'] == "uniswap":
        if not approve_token(USDC, UNISWAP_ROUTER, f['miktar_a']):
            return False
        basari = uniswap_swap(USDC, WETH, f['miktar_a'], f['beklenen_b'])
    else:
        if not approve_token(USDC, AERODROME_ROUTER, f['miktar_a']):
            return False
        basari = aerodrome_swap(USDC, WETH, f['miktar_a'], f['beklenen_b'])

    if not basari:
        log("❌ 1. swap başarısız!")
        return False

    time.sleep(3)
    adres = Web3.to_checksum_address(CUZDAN)
    weth_k = w3.eth.contract(address=WETH, abi=ERC20_ABI)
    weth_bal = weth_k.functions.balanceOf(adres).call()
    log(f"✅ WETH alındı: {weth_bal/1e18:.6f}")

    if weth_bal == 0:
        log("❌ WETH yok!")
        return False

    min_usdc = int(f['miktar_a'] * 0.99)

    if f['adim2_dex'] == "uniswap":
        if not approve_token(WETH, UNISWAP_ROUTER, weth_bal):
            return False
        basari2 = uniswap_swap(WETH, USDC, weth_bal, min_usdc)
    else:
        if not approve_token(WETH, AERODROME_ROUTER, weth_bal):
            return False
        basari2 = aerodrome_swap(WETH, USDC, weth_bal, min_usdc)

    if basari2:
        log("🎉 ARBİTRAJ TAMAMLANDI!")
    else:
        log("❌ 2. swap başarısız!")

    return basari2

def main():
    log("=" * 55)
    log("🤖 ARBİTRAJ BOTU v5")
    log("=" * 55)
    log(f"Cüzdan : {CUZDAN}")
    log(f"Min kar: %{MIN_KAR_YUZDE}")
    log(f"İşlem  : ${ISLEM_USDC} USDC")
    log(f"Tarama : {TARAMA_SURESI}s")
    log("=" * 55)

    if not w3.is_connected():
        log("❌ Bağlantı yok!")
        return

    log(f"✅ Bağlandı! Blok: #{w3.eth.block_number}")
    eth, usdc, weth = bakiye_goster()

    if usdc < ISLEM_USDC:
        log(f"❌ Yetersiz USDC! En az ${ISLEM_USDC} lazım. Mevcut: ${usdc:.2f}")
        return

    dongu = 0
    while True:
        dongu += 1
        log(f"\n🔄 Tarama #{dongu}")
        try:
            firsat = arbitraj_tara()
            if firsat:
                log(f"✅ FIRSAT: %{firsat['fark']:.3f}")
                arbitraj_yap(firsat)
                bakiye_goster()
            else:
                log("😴 Fırsat yok...")
        except KeyboardInterrupt:
            log("🛑 Durduruldu!")
            break
        except Exception as e:
            log(f"❌ Hata: {e}")
        time.sleep(TARAMA_SURESI)

if __name__ == "__main__":
    main()
