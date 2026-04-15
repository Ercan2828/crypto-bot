import requests
import time
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

def stuur_telegram(bericht):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": bericht, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

def haal_coins_op():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except:
        return []

def haal_historisch(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": 30, "interval": "daily"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [p[1] for p in data.get("prices", [])]
    except:
        return []

def bereken_rsi(prijzen, periode=14):
    if len(prijzen) < periode + 1:
        return 50
    winsten, verliezen = [], []
    for i in range(1, len(prijzen)):
        d = prijzen[i] - prijzen[i-1]
        winsten.append(max(d, 0))
        verliezen.append(max(-d, 0))
    gw = sum(winsten[-periode:]) / periode
    gv = sum(verliezen[-periode:]) / periode
    if gv == 0:
        return 100
    return round(100 - (100 / (1 + gw/gv)), 1)

def bereken_targets(prijs):
    stop_loss     = round(prijs * 0.85, 8)
    take_profit_1 = round(prijs * 1.30, 8)
    take_profit_2 = round(prijs * 1.75, 8)
    take_profit_3 = round(prijs * 2.50, 8)
    return stop_loss, take_profit_1, take_profit_2, take_profit_3

def analyseer_coin(coin):
    naam        = coin.get("name", "")
    symbool     = coin.get("symbol", "").upper()
    prijs       = coin.get("current_price", 0) or 0
    marktwaarde = coin.get("market_cap", 0) or 0
    volume      = coin.get("total_volume", 0) or 0
    change_1h   = coin.get("price_change_percentage_1h_in_currency", 0) or 0
    change_24h  = coin.get("price_change_percentage_24h", 0) or 0
    change_7d   = coin.get("price_change_percentage_7d_in_currency", 0) or 0

    if marktwaarde < 500_000 or marktwaarde > 800_000_000:
        return None
    if volume < 50_000 or prijs <= 0:
        return None

    time.sleep(1.5)
    historisch = haal_historisch(coin["id"])
    rsi = bereken_rsi(historisch)
    volume_ratio = volume / marktwaarde if marktwaarde > 0 else 0

    score = 0
    signalen = []

    if rsi < 25:
        score += 4
        signalen.append("🔥 RSI extreem oversold — sterke koopmogelijkheid")
    elif rsi < 35:
        score += 3
        signalen.append("🟢 RSI oversold — goed instapmoment")
    elif rsi < 45:
        score += 2
        signalen.append("🟡 RSI laag — opbouwen mogelijk")

    if volume_ratio > 0.5:
        score += 3
        signalen.append("💥 Extreem hoog volume — iemand koopt massaal")
    elif volume_ratio > 0.3:
        score += 2
        signalen.append("📊 Hoog handelsvolume — interesse groeit")

    if change_1h > 5:
        score += 2
        signalen.append(f"⚡ +{change_1h:.1f}% afgelopen uur — momentum!")
    if change_24h > 15:
        score += 2
        signalen.append(f"📈 +{change_24h:.1f}% vandaag — sterke beweging")
    elif change_24h > 5:
        score += 1
        signalen.append(f"📈 +{change_24h:.1f}% vandaag")
    if change_7d > 20:
        score += 2
        signalen.append(f"🚀 +{change_7d:.1f}% deze week — trending")

    if marktwaarde < 10_000_000:
        score += 2
        signalen.append("💎 Kleine marktwaarde — groot groeipotentieel")
    elif marktwaarde < 50_000_000:
        score += 1
        signalen.append("💎 Middelgrote marktwaarde — ruimte voor groei")

    if score < 5:
        return None

    kracht = "✅ GOEDE SETUP"
    if score >= 9:
        kracht = "🏆 GOUDEN SETUP"
    elif score >= 7:
        kracht = "🥇 STERKE SETUP"

    sl, tp1, tp2, tp3 = bereken_targets(prijs)

    return {
        "naam": naam, "symbool": symbool, "prijs": prijs,
        "rsi": rsi, "change_24h": change_24h, "change_7d": change_7d,
        "marktwaarde": marktwaarde, "score": score, "signalen": signalen,
        "kracht": kracht, "stop_loss": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
    }

def stuur_signaal(p):
    winst_tp1 = round(1000 * 0.30)
    winst_tp2 = round(1000 * 0.75)
    winst_tp3 = round(1000 * 1.50)
    verlies_sl = round(1000 * 0.15)

    bericht = f"""{p['kracht']}

🪙 <b>{p['naam']} ({p['symbool']})</b>
━━━━━━━━━━━━━━━━━━

📊 <b>MARKTINFO</b>
💰 Prijs nu: <b>${p['prijs']:.8f}</b>
📈 24u: {p['change_24h']:+.1f}% | 7d: {p['change_7d']:+.1f}%
📉 RSI: {p['rsi']} | Score: {p['score']}/12
💎 Marktwaarde: ${p['marktwaarde']:,.0f}

━━━━━━━━━━━━━━━━━━
🎯 <b>JOUW TRADE PLAN</b>

🟢 <b>KOOP NU bij:</b> ${p['prijs']:.8f}

🔴 <b>STOP-LOSS (-15%):</b> ${p['stop_loss']:.8f}
   Max verlies bij €1000: -€{verlies_sl}

✅ <b>TAKE PROFIT 1 (+30%):</b> ${p['tp1']:.8f}
   Winst bij €1000: +€{winst_tp1} → Verkoop 30%

🎯 <b>TAKE PROFIT 2 (+75%):</b> ${p['tp2']:.8f}
   Winst bij €1000: +€{winst_tp2} → Verkoop 40%

🚀 <b>TAKE PROFIT 3 (+150%):</b> ${p['tp3']:.8f}
   Winst bij €1000: +€{winst_tp3} → Laat de rest lopen!

━━━━━━━━━━━━━━━━━━
⚡ <b>SIGNALEN</b>
""" + "\n".join(p['signalen']) + "\n\n⚠️ Geen financieel advies. Investeer alleen wat je kunt missen."

    stuur_telegram(bericht)

def scan():
    print("Scan gestart...")
    stuur_telegram("🔍 <b>Hedge Fund Scanner actief</b>\nIk scan nu 250 munten op gouden kansen...")

    coins = haal_coins_op()
    gevonden = []

    for coin in coins:
        resultaat = analyseer_coin(coin)
        if resultaat:
            gevonden.append(resultaat)

    gevonden.sort(key=lambda x: x["score"], reverse=True)

    if gevonden:
        stuur_telegram(f"✅ <b>{len(gevonden)} kansen gevonden!</b> Top 5 komen eraan...")
        time.sleep(2)
        for p in gevonden[:5]:
            stuur_signaal(p)
            time.sleep(3)
    else:
        stuur_telegram("📭 Geen sterke setups nu. Volgende scan over 4 uur.")

    print(f"Klaar. {len(gevonden)} gevonden.")

def main():
    stuur_telegram("""🤖 <b>Jouw Crypto Hedge Fund Bot is LIVE!</b>

Ik scan elke 4 uur de markt en stuur je:
✅ Exacte koopmomenten
🎯 Take profit 1, 2 en 3
🔴 Stop-loss prijzen
📊 RSI analyse
💎 Verborgen gems

Eerste scan begint nu...""")

    while True:
        scan()
        print("Wacht 4 uur...")
        time.sleep(4 * 60 * 60)

if __name__ == "__main__":
    main()
