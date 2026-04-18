import os
import time
import requests
import threading
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

portfolio = {}

BITVAVO_COINS = [
    "bitcoin", "ethereum", "solana", "ripple", "cardano",
    "polkadot", "chainlink", "avalanche-2", "uniswap", "litecoin",
    "stellar", "vechain", "filecoin", "aave", "the-graph",
    "maker", "compound-governance-token", "yearn-finance", "sushi",
    "1inch", "curve-dao-token", "convex-finance", "lido-dao",
    "render-token", "injective-protocol", "aptos", "arbitrum",
    "optimism", "polygon", "near", "internet-computer",
    "cosmos", "algorand", "tezos", "elrond-erd-2",
    "flow", "helium", "theta-token", "chiliz", "sandbox",
    "decentraland", "axie-infinity", "gala", "enjincoin",
    "basic-attention-token", "ocean-protocol", "fetch-ai",
    "singularitynet", "numeraire"
]

def stuur_telegram(bericht):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram niet geconfigureerd")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": bericht[:4000], "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        print(f"Telegram fout: {e}")

def vraag_ai(vraag):
    if not ANTHROPIC_API_KEY:
        return "AI niet beschikbaar — API key ontbreekt."
    try:
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        systeem = """Je bent een persoonlijke crypto hedge fund AI voor Ercan in Nederland.
Je spreekt altijd Nederlands. Je analyseert coins die beschikbaar zijn op Bitvavo en Kraken.
Je geeft altijd: entry prijs, stop-loss (-15%), take profit 1 (+30%), 2 (+75%), 3 (+150%).
Je denkt als smart money — je zoekt vroege signalen VOOR de stijging.
Je bent eerlijk over risicos maar ook enthousiast over echte kansen.
Houd antwoorden overzichtelijk en niet te lang."""

        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 800,
            "system": systeem,
            "messages": [{"role": "user", "content": vraag}]
        }
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=30
        )
        if resp.status_code != 200:
            return f"API fout {resp.status_code}. Probeer opnieuw."
        data = resp.json()
        if "content" not in data or not data["content"]:
            return "Geen antwoord ontvangen. Probeer opnieuw."
        return data["content"][0]["text"]
    except Exception as e:
        print(f"AI fout: {e}")
        return "Even geen verbinding. Probeer opnieuw!"

def haal_coin_data(coin_ids):
    try:
        ids = ",".join(coin_ids)
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": ids,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return {}
        data = r.json()
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        print(f"CoinGecko fout: {e}")
        return {}

def bereken_rsi_simpel(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": 14, "interval": "daily"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return 50
        data = r.json()
        if not isinstance(data, dict):
            return 50
        prijzen = [p[1] for p in data.get("prices", []) if isinstance(p, list) and len(p) >= 2]
        if len(prijzen) < 15:
            return 50
        winsten, verliezen = [], []
        for i in range(1, len(prijzen)):
            d = prijzen[i] - prijzen[i-1]
            winsten.append(max(d, 0))
            verliezen.append(max(-d, 0))
        gw = sum(winsten[-14:]) / 14
        gv = sum(verliezen[-14:]) / 14
        if gv == 0:
            return 100
        return round(100 - (100 / (1 + gw/gv)), 1)
    except:
        return 50

def scan_bitvavo():
    print(f"Scan gestart: {datetime.now().strftime('%H:%M:%S')}")
    stuur_telegram("🔍 <b>Bitvavo scanner actief</b> — Vroege signalen zoeken...")

    gevonden = []

    batches = [BITVAVO_COINS[i:i+10] for i in range(0, len(BITVAVO_COINS), 10)]

    for batch in batches:
        data = haal_coin_data(batch)
        if not data:
            time.sleep(2)
            continue

        for coin_id in batch:
            try:
                if coin_id not in data:
                    continue
                coin = data[coin_id]
                if not isinstance(coin, dict):
                    continue

                prijs = coin.get("usd", 0) or 0
                change_24h = coin.get("usd_24h_change", 0) or 0
                volume = coin.get("usd_24h_vol", 0) or 0
                marktwaarde = coin.get("usd_market_cap", 0) or 0

                if prijs <= 0 or volume < 100000:
                    continue

                time.sleep(1.5)
                rsi = bereken_rsi_simpel(coin_id)

                volume_ratio = volume / marktwaarde if marktwaarde > 0 else 0

                score = 0
                signalen = []

                if rsi < 30:
                    score += 4
                    signalen.append("🔥 RSI extreem laag — koopmogelijkheid")
                elif rsi < 40:
                    score += 3
                    signalen.append("🟢 RSI laag — goed instapmoment")
                elif rsi < 50:
                    score += 1
                    signalen.append("🟡 RSI neutraal")

                if volume_ratio > 0.3:
                    score += 3
                    signalen.append("💥 Hoog volume — interesse stijgt")
                elif volume_ratio > 0.15:
                    score += 2
                    signalen.append("📊 Volume neemt toe")

                if 2 < change_24h < 15:
                    score += 2
                    signalen.append(f"📈 +{change_24h:.1f}% vandaag — gezonde stijging")
                elif 15 <= change_24h < 30:
                    score += 1
                    signalen.append(f"🚀 +{change_24h:.1f}% vandaag")
                elif change_24h < -5:
                    score += 1
                    signalen.append(f"📉 {change_24h:.1f}% daling — mogelijke bounce")

                if score >= 5:
                    naam = coin_id.replace("-", " ").title()
                    sl = round(prijs * 0.85, 8)
                    tp1 = round(prijs * 1.30, 8)
                    tp2 = round(prijs * 1.75, 8)
                    tp3 = round(prijs * 2.50, 8)

                    gevonden.append({
                        "naam": naam,
                        "coin_id": coin_id,
                        "prijs": prijs,
                        "rsi": rsi,
                        "change_24h": change_24h,
                        "score": score,
                        "signalen": signalen,
                        "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
                    })
            except Exception as e:
                print(f"Fout bij {coin_id}: {e}")
                continue

        time.sleep(3)

    gevonden.sort(key=lambda x: x["score"], reverse=True)

    if gevonden:
        stuur_telegram(f"✅ <b>{len(gevonden)} kansen gevonden op Bitvavo!</b> Top 3 komen eraan...")
        time.sleep(2)
        for p in gevonden[:3]:
            bericht = f"""🏆 <b>VROEG SIGNAAL — BITVAVO</b>

🪙 <b>{p['naam']}</b>
━━━━━━━━━━━━━━━━━━

📊 <b>MARKTDATA</b>
💰 Prijs: <b>${p['prijs']:.6f}</b>
📈 24u: {p['change_24h']:+.1f}%
📉 RSI: {p['rsi']} | Score: {p['score']}/9

━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE PLAN</b>

🟢 <b>KOOP NU:</b> ${p['prijs']:.6f}
🔴 <b>STOP-LOSS (-15%):</b> ${p['sl']:.6f}
✅ <b>TP1 (+30%):</b> ${p['tp1']:.6f} → Verkoop 30%
🎯 <b>TP2 (+75%):</b> ${p['tp2']:.6f} → Verkoop 40%
🚀 <b>TP3 (+150%):</b> ${p['tp3']:.6f} → Laat lopen!

━━━━━━━━━━━━━━━━━━
⚡ <b>SIGNALEN</b>
""" + "\n".join(p['signalen']) + """

💬 Typ: analyseer """ + p['naam'] + """ voor AI analyse
⚠️ Geen financieel advies."""
            stuur_telegram(bericht)
            time.sleep(3)
    else:
        stuur_telegram("📭 Geen sterke signalen nu. Volgende scan over 30 minuten.")

    print(f"Scan klaar: {len(gevonden)} gevonden")

def verwerk_bericht(tekst):
    tekst_lower = tekst.lower().strip()

    if tekst_lower in ["/start", "hallo", "hoi", "hey", "hi"]:
        stuur_telegram("""👋 <b>Hallo Ercan! Jouw Hedge Fund AI</b>

<b>COMMANDO'S:</b>
🔍 /scan — Start scan nu
📊 analyseer [coin] — AI analyse
💼 /portfolio — Jouw portfolio
💡 /advies — Markt advies
📰 /nieuws — Crypto nieuws

<b>PORTFOLIO:</b>
koop BTC 65000 — Toevoegen
verkoop BTC — Verwijderen

Of stel gewoon een vraag! 💬
Scans lopen automatisch om 07:00 en 00:00""")

    elif tekst_lower == "/scan":
        stuur_telegram("🔍 Handmatige scan gestart...")
        threading.Thread(target=scan_bitvavo, daemon=True).start()

    elif tekst_lower.startswith("analyseer ") or tekst_lower.startswith("/analyseer "):
        coin = tekst.replace("/analyseer", "").replace("analyseer", "").strip()
        if coin:
            stuur_telegram(f"🔍 Analyseer {coin}...")
            antwoord = vraag_ai(f"Analyseer {coin} voor mij. Geef: huidige trend, RSI inschatting, is het nu een goed instapmoment, entry prijs, stop-loss en take profit levels. Beschikbaar op Bitvavo of Kraken?")
            stuur_telegram(f"📊 <b>Analyse {coin.upper()}</b>\n\n{antwoord}")
        else:
            stuur_telegram("Welke coin? Bijv: analyseer BTC")

    elif tekst_lower == "/portfolio":
        if portfolio:
            bericht = "💼 <b>Jouw Portfolio</b>\n\n"
            for coin, data in portfolio.items():
                bericht += f"🪙 <b>{coin}</b>\nIngekocht: ${data['prijs']:.6f}\nStop-loss: ${data['sl']:.6f}\nDatum: {data['tijd']}\n\n"
            stuur_telegram(bericht)
        else:
            stuur_telegram("Portfolio leeg.\nToevoegen: koop BTC 65000")

    elif tekst_lower == "/advies":
        antwoord = vraag_ai("Geef algemeen markt advies voor nu. Wat is het sentiment? Waar zijn de kansen op Bitvavo? Wat moet ik vermijden?")
        stuur_telegram(f"💡 <b>Markt Advies</b>\n\n{antwoord}")

    elif tekst_lower == "/nieuws":
        antwoord = vraag_ai("Wat is het meest relevante crypto nieuws van vandaag? Top 5 items met uitleg wat dit betekent voor de markt.")
        stuur_telegram(f"📰 <b>Crypto Nieuws</b>\n\n{antwoord}")

    elif tekst_lower.startswith("koop "):
        delen = tekst.split()
        if len(delen) >= 3:
            coin = delen[1].upper()
            try:
                prijs = float(delen[2])
                sl = round(prijs * 0.85, 8)
                portfolio[coin] = {
                    "prijs": prijs,
                    "sl": sl,
                    "tijd": datetime.now().strftime("%d/%m %H:%M")
                }
                stuur_telegram(f"✅ <b>{coin} toegevoegd!</b>\nIngekocht: ${prijs:.6f}\nStop-loss: ${sl:.6f}")
            except:
                stuur_telegram("Gebruik: koop BTC 65000")
        else:
            stuur_telegram("Gebruik: koop BTC 65000")

    elif tekst_lower.startswith("verkoop "):
        delen = tekst.split()
        if len(delen) >= 2:
            coin = delen[1].upper()
            if coin in portfolio:
                del portfolio[coin]
                stuur_telegram(f"✅ {coin} verwijderd uit portfolio.")
            else:
                stuur_telegram(f"{coin} staat niet in je portfolio.")

    else:
        stuur_telegram("🤔 Even nadenken...")
        antwoord = vraag_ai(tekst)
        stuur_telegram(f"🤖 <b>Hedge Fund AI</b>\n\n{antwoord}")

def luister_telegram():
    offset = None
    print("Luisteren naar Telegram berichten...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            resp = requests.get(url, params=params, timeout=35)
            if resp.status_code != 200:
                time.sleep(5)
                continue
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    tekst = update["message"]["text"]
                    print(f"Bericht: {tekst}")
                    try:
                        verwerk_bericht(tekst)
                    except Exception as e:
                        print(f"Fout bericht: {e}")
        except Exception as e:
            print(f"Luister fout: {e}")
            time.sleep(10)

def geplande_scans():
    laatste_07 = None
    laatste_00 = None
    while True:
        try:
            nu = datetime.now()
            dag_uur = f"{nu.date()}-{nu.hour}"

            if nu.hour == 7 and dag_uur != laatste_07:
                laatste_07 = dag_uur
                print("Ochtend scan 07:00")
                scan_bitvavo()

            if nu.hour == 0 and dag_uur != laatste_00:
                laatste_00 = dag_uur
                print("Nacht scan 00:00")
                scan_bitvavo()

        except Exception as e:
            print(f"Geplande scan fout: {e}")

        time.sleep(60)

def main():
    print("Bot gestart!")
    stuur_telegram("""🤖 <b>Hedge Fund AI — LIVE op Bitvavo!</b>

✅ Scant Bitvavo coins op vroege signalen
✅ Ochtend scan om 07:00
✅ Nacht scan om 00:00
✅ Koop/stop-loss/take profit signalen
✅ AI gesprek — stel alles wat je wil
✅ Portfolio tracker

Stuur /start voor alle commando's!
Eerste scan begint nu... 🚀""")

    threading.Thread(target=luister_telegram, daemon=True).start()
    threading.Thread(target=geplande_scans, daemon=True).start()

    scan_bitvavo()

    while True:
        time.sleep(30 * 60)
        try:
            scan_bitvavo()
        except Exception as e:
            print(f"Scan fout: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
