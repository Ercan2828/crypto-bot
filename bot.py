import os
import time
import requests
import threading
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

portfolio = {}

BITVAVO_COINS = [
    "bitcoin", "ethereum", "solana", "ripple", "cardano",
    "polkadot", "chainlink", "avalanche-2", "uniswap", "litecoin",
    "stellar", "vechain", "filecoin", "aave", "the-graph",
    "maker", "compound-governance-token", "yearn-finance", "sushi",
    "1inch", "curve-dao-token", "lido-dao", "render-token",
    "injective-protocol", "aptos", "arbitrum", "optimism",
    "polygon", "near", "internet-computer", "cosmos", "algorand",
    "tezos", "flow", "chiliz", "sandbox", "decentraland",
    "axie-infinity", "gala", "enjincoin", "basic-attention-token",
    "ocean-protocol", "fetch-ai", "singularitynet", "pepe",
    "shiba-inu", "dogecoin", "floki", "bonk"
]

def stuur_telegram(bericht):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": bericht[:4000], "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        print(f"Telegram fout: {e}")

def haal_btc_prijs():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if isinstance(data, dict) and "bitcoin" in data:
            prijs = data["bitcoin"].get("usd", 0)
            return f"{prijs:,.0f}"
        return "onbekend"
    except:
        return "onbekend"

def haal_live_nieuws():
    resultaten = []
    if NEWS_API_KEY:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": "crypto OR bitcoin OR ethereum OR altcoin",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 8,
                "apiKey": NEWS_API_KEY
            }
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for artikel in data.get("articles", [])[:5]:
                    titel = artikel.get("title", "")
                    bron = artikel.get("source", {}).get("name", "")
                    if titel and "[Removed]" not in titel:
                        resultaten.append(f"- {titel} ({bron})")
        except Exception as e:
            print(f"NewsAPI fout: {e}")
    if not resultaten:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/news", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for item in data[:5]:
                        if isinstance(item, dict):
                            titel = item.get("title", "")
                            if titel:
                                resultaten.append(f"- {titel}")
        except:
            pass
    return "\n".join(resultaten) if resultaten else "Geen live nieuws beschikbaar."

def vraag_ai(vraag, extra_context=""):
    if not ANTHROPIC_API_KEY:
        return "AI niet beschikbaar."
    try:
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        systeem = f"""Je bent een persoonlijke crypto hedge fund AI voor Ercan in Nederland.
Je spreekt altijd Nederlands.
Je doel: Ercan zoveel mogelijk geld laten verdienen met crypto op Bitvavo.
Je geeft altijd: exacte entry prijs, stop-loss (-15%), TP1 (+30%), TP2 (+75%), TP3 (+150%).
Je zoekt explosievolle kansen die 2x-5x kunnen gaan.
Je bent eerlijk en direct — geen omwegen.
{extra_context}"""

        body = {
            "model": "claude-sonnet-4-5",
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
            return "Geen antwoord. Probeer opnieuw."
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

def haal_uur_data(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": 1, "interval": "hourly"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None, None
        data = r.json()
        if not isinstance(data, dict):
            return None, None
        volumes = [v[1] for v in data.get("total_volumes", []) if isinstance(v, list) and len(v) >= 2]
        prijzen = [p[1] for p in data.get("prices", []) if isinstance(p, list) and len(p) >= 2]
        return volumes, prijzen
    except:
        return None, None

def bereken_rsi(prijzen, periode=14):
    try:
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
    except:
        return 50

def scan_bitvavo():
    print(f"Scan: {datetime.now().strftime('%H:%M:%S')}")
    stuur_telegram("🔍 <b>Scanner actief</b> — Explosieve kansen zoeken...")

    gevonden = []
    batches = [BITVAVO_COINS[i:i+10] for i in range(0, len(BITVAVO_COINS), 10)]

    for batch in batches:
        data = haal_coin_data(batch)
        if not data:
            time.sleep(3)
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
                volume_24h = coin.get("usd_24h_vol", 0) or 0

                if prijs <= 0 or volume_24h < 10000:
                    continue

                time.sleep(1.5)
                volumes_uur, prijzen_uur = haal_uur_data(coin_id)

                signalen = []
                score = 0

                # Check volume explosie in laatste uur
                volume_explosie = False
                if volumes_uur and len(volumes_uur) >= 3:
                    gem_volume = sum(volumes_uur[-6:-1]) / 5 if len(volumes_uur) >= 6 else sum(volumes_uur[:-1]) / max(len(volumes_uur)-1, 1)
                    laatste_volume = volumes_uur[-1]
                    if gem_volume > 0 and laatste_volume > gem_volume * 1.5:
                        score += 4
                        pct = round((laatste_volume / gem_volume - 1) * 100)
                        signalen.append(f"💥 Volume +{pct}% in laatste uur — iets gaat gebeuren!")
                        volume_explosie = True

                # RSI check
                rsi = 50
                if prijzen_uur and len(prijzen_uur) >= 15:
                    rsi = bereken_rsi(prijzen_uur)
                    if rsi < 30:
                        score += 3
                        signalen.append(f"🔥 RSI {rsi} — extreem oversold, bounce verwacht")
                    elif rsi < 45:
                        score += 2
                        signalen.append(f"🟢 RSI {rsi} — laag, goed instapmoment")

                # Prijs beweging
                if 2 < change_24h < 20:
                    score += 2
                    signalen.append(f"📈 +{change_24h:.1f}% vandaag — momentum start")
                elif change_24h >= 20:
                    score += 1
                    signalen.append(f"🚀 +{change_24h:.1f}% vandaag")
                elif -10 < change_24h < -3:
                    score += 1
                    signalen.append(f"📉 {change_24h:.1f}% daling — bounce kans")

                # Uur beweging
                if prijzen_uur and len(prijzen_uur) >= 2:
                    change_1h = round((prijzen_uur[-1] / prijzen_uur[-2] - 1) * 100, 2) if prijzen_uur[-2] > 0 else 0
                    if change_1h > 3:
                        score += 2
                        signalen.append(f"⚡ +{change_1h:.1f}% afgelopen uur — momentum!")
                    elif change_1h > 1:
                        score += 1
                        signalen.append(f"⚡ +{change_1h:.1f}% afgelopen uur")

                # Alleen sturen als er echt iets aan de hand is
                if score >= 4 and signalen:
                    naam = coin_id.replace("-", " ").title()
                    sl = round(prijs * 0.85, 8)
                    tp1 = round(prijs * 1.30, 8)
                    tp2 = round(prijs * 1.75, 8)
                    tp3 = round(prijs * 2.50, 8)

                    gevonden.append({
                        "naam": naam,
                        "prijs": prijs,
                        "rsi": rsi,
                        "change_24h": change_24h,
                        "score": score,
                        "signalen": signalen,
                        "volume_explosie": volume_explosie,
                        "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
                    })

            except Exception as e:
                print(f"Fout {coin_id}: {e}")
                continue

        time.sleep(3)

    gevonden.sort(key=lambda x: x["score"], reverse=True)

    if gevonden:
        stuur_telegram(f"🚨 <b>{len(gevonden)} EXPLOSIEVE KANSEN gevonden!</b> Top 3 komen eraan...")
        time.sleep(2)
        for p in gevonden[:3]:
            emoji = "🚨" if p["volume_explosie"] else "🏆"
            bericht = f"""{emoji} <b>VROEG SIGNAAL — BITVAVO</b>

🪙 <b>{p['naam']}</b>
━━━━━━━━━━━━━━━━━━

💰 Prijs nu: <b>${p['prijs']:.6f}</b>
📈 24u: {p['change_24h']:+.1f}%
📉 RSI: {p['rsi']}

━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE PLAN</b>

🟢 <b>KOOP NU:</b> ${p['prijs']:.6f}
🔴 <b>STOP-LOSS (-15%):</b> ${p['sl']:.6f}
✅ <b>TP1 (+30%):</b> ${p['tp1']:.6f} → Verkoop 30%
🎯 <b>TP2 (+75%):</b> ${p['tp2']:.6f} → Verkoop 40%
🚀 <b>TP3 (+150%):</b> ${p['tp3']:.6f} → Laat lopen!

━━━━━━━━━━━━━━━━━━
⚡ <b>SIGNALEN</b>
""" + "\n".join(p['signalen']) + f"""

💬 Typ: analyseer {p['naam']} voor AI analyse
⚠️ Geen financieel advies."""
            stuur_telegram(bericht)
            time.sleep(3)
    else:
        stuur_telegram("📭 Geen explosieve signalen nu. Volgende scan over 30 minuten.")

    print(f"Scan klaar: {len(gevonden)} gevonden")

def verwerk_bericht(tekst):
    tekst_lower = tekst.lower().strip()

    if tekst_lower in ["/start", "hallo", "hoi", "hey", "hi"]:
        stuur_telegram("""👋 <b>Hallo Ercan! Jouw Hedge Fund AI</b>

<b>COMMANDO'S:</b>
🔍 /scan — Start scan nu
📊 analyseer [coin] — Diepere analyse
💼 /portfolio — Jouw portfolio
💡 /advies — Markt advies
📰 /nieuws — Live crypto nieuws
📈 /btc — Bitcoin prijs nu

<b>PORTFOLIO:</b>
koop BTC 65000 — Toevoegen
verkoop BTC — Verwijderen

Of stel gewoon een vraag! 💬
Automatische scans: 07:00 en 00:00""")

    elif tekst_lower == "/scan":
        stuur_telegram("🔍 Handmatige scan gestart...")
        threading.Thread(target=scan_bitvavo, daemon=True).start()

    elif tekst_lower == "/btc":
        prijs = haal_btc_prijs()
        stuur_telegram(f"₿ <b>Bitcoin prijs nu: ${prijs}</b>")

    elif tekst_lower.startswith("analyseer ") or tekst_lower.startswith("/analyseer "):
        coin = tekst.replace("/analyseer", "").replace("analyseer", "").strip()
        if coin:
            stuur_telegram(f"🔍 Analyseer {coin}...")
            btc = haal_btc_prijs()
            antwoord = vraag_ai(
                f"Analyseer {coin} voor mij. Is dit nu een explosieve kans? Geef entry, stop-loss en take profit levels.",
                extra_context=f"Live BTC prijs: ${btc}"
            )
            stuur_telegram(f"📊 <b>Analyse {coin.upper()}</b>\n\n{antwoord}")
        else:
            stuur_telegram("Welke coin? Bijv: analyseer SOL")

    elif tekst_lower == "/portfolio":
        if portfolio:
            bericht = "💼 <b>Jouw Portfolio</b>\n\n"
            for coin, d in portfolio.items():
                bericht += f"🪙 <b>{coin}</b>\nIngekocht: ${d['prijs']:.6f}\nStop-loss: ${d['sl']:.6f}\nDatum: {d['tijd']}\n\n"
            stuur_telegram(bericht)
        else:
            stuur_telegram("Portfolio leeg.\nToevoegen: koop BTC 65000")

    elif tekst_lower == "/advies":
        stuur_telegram("💡 Advies ophalen...")
        btc = haal_btc_prijs()
        nieuws = haal_live_nieuws()
        antwoord = vraag_ai(
            "Geef markt advies. Waar zijn de explosieve kansen nu op Bitvavo? Welke coins kunnen 2x-5x gaan?",
            extra_context=f"Live BTC prijs: ${btc}\n\nLive nieuws:\n{nieuws}"
        )
        stuur_telegram(f"💡 <b>Markt Advies</b>\n\n{antwoord}")

    elif tekst_lower == "/nieuws":
        stuur_telegram("📰 Nieuws ophalen...")
        btc = haal_btc_prijs()
        nieuws = haal_live_nieuws()
        antwoord = vraag_ai(
            f"Hier is het live nieuws van vandaag:\n{nieuws}\n\nBTC staat nu op ${btc}.\n\nWat betekent dit nieuws voor de crypto markt? Welke coins profiteer hiervan?",
            extra_context=f"Live BTC: ${btc}"
        )
        stuur_telegram(f"📰 <b>Live Nieuws Analyse</b>\n\n{antwoord}")

    elif tekst_lower.startswith("koop "):
        delen = tekst.split()
        if len(delen) >= 3:
            coin = delen[1].upper()
            try:
                prijs = float(delen[2])
                sl = round(prijs * 0.85, 8)
                portfolio[coin] = {"prijs": prijs, "sl": sl, "tijd": datetime.now().strftime("%d/%m %H:%M")}
                stuur_telegram(f"✅ <b>{coin} toegevoegd!</b>\nIngekocht: ${prijs:.6f}\nStop-loss: ${sl:.6f}")
            except:
                stuur_telegram("Gebruik: koop SOL 150")
        else:
            stuur_telegram("Gebruik: koop SOL 150")

    elif tekst_lower.startswith("verkoop "):
        delen = tekst.split()
        if len(delen) >= 2:
            coin = delen[1].upper()
            if coin in portfolio:
                del portfolio[coin]
                stuur_telegram(f"✅ {coin} verwijderd.")
            else:
                stuur_telegram(f"{coin} staat niet in je portfolio.")

    else:
        stuur_telegram("🤔 Even nadenken...")
        btc = haal_btc_prijs()
        nieuws = haal_live_nieuws()
        antwoord = vraag_ai(
            tekst,
            extra_context=f"Live BTC prijs: ${btc}\n\nLive nieuws:\n{nieuws}"
        )
        stuur_telegram(f"🤖 <b>Hedge Fund AI</b>\n\n{antwoord}")

def luister_telegram():
    offset = None
    print("Luisteren...")
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
                        print(f"Fout: {e}")
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
                scan_bitvavo()
            if nu.hour == 0 and dag_uur != laatste_00:
                laatste_00 = dag_uur
                scan_bitvavo()
        except Exception as e:
            print(f"Scan fout: {e}")
        time.sleep(60)

def main():
    print("Bot gestart!")
    stuur_telegram("""🚀 <b>Hedge Fund AI — LIVE!</b>

✅ Zoekt explosieve 2x-5x kansen
✅ Volume explosie detector
✅ RSI + momentum analyse
✅ Live nieuws via NewsAPI
✅ Live BTC prijs
✅ Scans om 07:00 en 00:00
✅ Praat met mij via Telegram

Stuur /start voor commando's!
Eerste scan begint nu...""")

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
