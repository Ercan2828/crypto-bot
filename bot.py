import os
import time
import requests
import json
import threading
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

portfolio = {}
meme_modus = False
gevolgde_wallets = []

MEME_TRADERS = [
    "gainzy222", "cobie", "hsaka", "cryptokaleo",
    "inversebrah", "lightcrypto", "blknoiz06"
]

def stuur_telegram(bericht):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": bericht, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

def vraag_ai(vraag, context="", meme=False):
    try:
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        if meme:
            systeem = """Je bent een persoonlijke crypto hedge fund AI voor Ercan, gespecialiseerd in MEME COINS.
Je spreekt Nederlands. Je bent zijn persoonlijke meme coin analist.
Je geeft altijd:
- Entry prijs
- Stop-loss (snel, -20% want meme coins bewegen snel)
- Take profit 1 (+50%), 2 (+150%), 3 (+300%)
- Risico waarschuwing (meme coins zijn HOOG RISICO)
- Of het een rugpull risico heeft
- Hoeveel liquiditeit er is
Je volgt DexScreener, grote meme traders en on-chain signals.
Wees eerlijk: meme coins kunnen 10x gaan maar ook naar 0."""
        else:
            systeem = """Je bent een persoonlijke crypto hedge fund AI assistent voor Ercan.
Je spreekt Nederlands. Je bent zijn persoonlijke AI analist.
Je geeft altijd duidelijke, overzichtelijke antwoorden met:
- Exacte koop/verkoop prijzen
- Stop-loss levels
- Take profit 1, 2 en 3
- Risico inschatting (Veilig/Medium/High Risk)
- Jouw eerlijke mening
- On-chain signalen als relevant
Je volgt: Bitvavo, Binance, Bybit, KuCoin, Kraken, MEXC, OKX, Uniswap, PancakeSwap, DexScreener.
Je analyseert: RSI, volume, marktwaarde, nieuws, social media, on-chain data.
Denk als een smart money insider die publieke data slim combineert.
Houd antwoorden overzichtelijk maar compleet."""

        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "system": systeem,
            "messages": [{"role": "user", "content": f"{context}\n\nVraag: {vraag}"}]
        }
        resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=30)
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as e:
        return f"Verbindingsfout. Probeer opnieuw! ({str(e)[:50]})"

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
    params = {"vs_currency": "usd", "days": 14, "interval": "daily"}
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

def haal_dexscreener_trending():
    try:
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list):
            return data[:20]
        return []
    except:
        return []

def haal_dexscreener_nieuw():
    try:
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list):
            return data[:10]
        return []
    except:
        return []

def analyseer_meme_coin(token):
    try:
        naam = token.get("description", "")[:30] or "Onbekend"
        symbool = ""
        chain = token.get("chainId", "")
        adres = token.get("tokenAddress", "")

        if not adres:
            return None

        detail_url = f"https://api.dexscreener.com/latest/dex/tokens/{adres}"
        r = requests.get(detail_url, timeout=10)
        detail = r.json()
        pairs = detail.get("pairs", [])

        if not pairs:
            return None

        pair = pairs[0]
        prijs = float(pair.get("priceUsd", 0) or 0)
        volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        liquiditeit = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
        change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        symbool = pair.get("baseToken", {}).get("symbol", "???")
        naam = pair.get("baseToken", {}).get("name", naam)
        dex_url = pair.get("url", "")

        if liquiditeit < 10000:
            return None
        if prijs <= 0:
            return None

        score = 0
        signalen = []
        risico = "🔴 HOOG RISICO"

        if liquiditeit > 100000:
            score += 2
            signalen.append(f"💧 Goede liquiditeit: ${liquiditeit:,.0f}")
        elif liquiditeit > 50000:
            score += 1
            signalen.append(f"💧 Liquiditeit: ${liquiditeit:,.0f}")

        if volume_24h > liquiditeit * 2:
            score += 3
            signalen.append("🔥 Extreem hoog volume vs liquiditeit!")
        elif volume_24h > liquiditeit:
            score += 2
            signalen.append("📊 Hoog handelsvolume")

        if 5 < change_1h < 50:
            score += 2
            signalen.append(f"⚡ +{change_1h:.1f}% laatste uur — momentum!")
        elif change_1h > 50:
            score += 1
            signalen.append(f"🚀 +{change_1h:.1f}% — al hard gestegen")

        if change_24h > 100:
            score += 1
            signalen.append(f"📈 +{change_24h:.1f}% vandaag")

        if liquiditeit > 200000 and volume_24h > 500000:
            risico = "🟡 MEDIUM RISICO"

        if score < 4:
            return None

        sl = round(prijs * 0.80, 12)
        tp1 = round(prijs * 1.50, 12)
        tp2 = round(prijs * 2.50, 12)
        tp3 = round(prijs * 4.00, 12)

        return {
            "naam": naam, "symbool": symbool, "prijs": prijs,
            "volume": volume_24h, "liquiditeit": liquiditeit,
            "change_1h": change_1h, "change_24h": change_24h,
            "score": score, "signalen": signalen, "risico": risico,
            "chain": chain, "adres": adres, "dex_url": dex_url,
            "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
        }
    except:
        return None

def stuur_meme_signaal(p):
    bericht = f"""🎭 <b>MEME COIN SIGNAAL</b>
{p['risico']}

🪙 <b>{p['naam']} ({p['symbool']})</b>
🌐 Chain: {p['chain']}

📊 <b>LIVE DATA (DexScreener)</b>
💰 Prijs: ${p['prijs']:.12f}
⚡ 1u: {p['change_1h']:+.1f}% | 24u: {p['change_24h']:+.1f}%
💧 Liquiditeit: ${p['liquiditeit']:,.0f}
📊 Volume 24u: ${p['volume']:,.0f}

━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE PLAN</b>

🟢 <b>ENTRY:</b> ${p['prijs']:.12f}
🔴 <b>STOP-LOSS (-20%):</b> ${p['sl']:.12f}
✅ <b>TP1 (+50%):</b> ${p['tp1']:.12f} → Verkoop 40%
🎯 <b>TP2 (+150%):</b> ${p['tp2']:.12f} → Verkoop 40%
🚀 <b>TP3 (+300%):</b> ${p['tp3']:.12f} → Laat 20% lopen!

━━━━━━━━━━━━━━━━━━
⚡ <b>SIGNALEN</b>
""" + "\n".join(p['signalen']) + f"""

━━━━━━━━━━━━━━━━━━
🔗 Contract: <code>{p['adres'][:20]}...</code>
⚠️ MEME COINS ZIJN EXTREEM RISICOVOL. Investeer nooit meer dan je kunt verliezen!"""

    stuur_telegram(bericht)

def analyseer_vroeg_signaal(coin):
    naam = coin.get("name", "")
    symbool = coin.get("symbol", "").upper()
    prijs = coin.get("current_price", 0) or 0
    marktwaarde = coin.get("market_cap", 0) or 0
    volume = coin.get("total_volume", 0) or 0
    change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0
    change_24h = coin.get("price_change_percentage_24h", 0) or 0
    change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0

    if marktwaarde < 100_000 or marktwaarde > 500_000_000:
        return None
    if volume < 50_000 or prijs <= 0:
        return None

    time.sleep(1)
    historisch = haal_historisch(coin["id"])
    rsi = bereken_rsi(historisch)
    volume_ratio = volume / marktwaarde if marktwaarde > 0 else 0

    score = 0
    signalen = []

    if rsi < 30:
        score += 4
        signalen.append("🔥 RSI extreem laag — nog niet ontdekt")
    elif rsi < 40:
        score += 3
        signalen.append("🟢 RSI laag — vroeg instapmoment")
    elif rsi < 50:
        score += 1
        signalen.append("🟡 RSI neutraal")

    if volume_ratio > 0.5:
        score += 3
        signalen.append("💥 Extreem hoog volume — smart money koopt")
    elif volume_ratio > 0.3:
        score += 2
        signalen.append("📊 Volume stijgt — vroeg signaal")
    elif volume_ratio > 0.15:
        score += 1
        signalen.append("📈 Volume neemt toe")

    if 2 < change_1h < 10:
        score += 2
        signalen.append(f"⚡ +{change_1h:.1f}% laatste uur — momentum start")
    elif change_1h > 10:
        score += 1
        signalen.append(f"🚀 +{change_1h:.1f}% laatste uur")

    if 5 < change_24h < 30:
        score += 2
        signalen.append(f"📈 +{change_24h:.1f}% vandaag — gezonde stijging")
    elif change_24h > 0:
        score += 1

    if marktwaarde < 5_000_000:
        score += 3
        signalen.append("💎 Micro cap — enorm groeipotentieel")
    elif marktwaarde < 20_000_000:
        score += 2
        signalen.append("💎 Klein project — veel ruimte omhoog")
    elif marktwaarde < 100_000_000:
        score += 1
        signalen.append("💎 Mid cap — nog ruimte")

    if score < 6:
        return None

    if marktwaarde < 10_000_000 and rsi < 35:
        trade_type = "🚀 HIGH RISK HIGH REWARD"
    elif marktwaarde < 100_000_000 and rsi < 45:
        trade_type = "⚖️ MEDIUM RISK"
    else:
        trade_type = "✅ VEILIGE TRADE"

    if score >= 10:
        kracht = "🏆 GOUDEN SETUP — VROEG SIGNAAL"
    elif score >= 8:
        kracht = "🥇 STERKE SETUP"
    else:
        kracht = "✅ GOEDE SETUP"

    sl = round(prijs * 0.85, 8)
    tp1 = round(prijs * 1.30, 8)
    tp2 = round(prijs * 1.75, 8)
    tp3 = round(prijs * 2.50, 8)

    return {
        "naam": naam, "symbool": symbool, "prijs": prijs,
        "rsi": rsi, "change_1h": change_1h, "change_24h": change_24h,
        "change_7d": change_7d, "marktwaarde": marktwaarde,
        "score": score, "signalen": signalen, "kracht": kracht,
        "trade_type": trade_type, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
    }

def stuur_signaal(p):
    bericht = f"""{p['kracht']}
{p['trade_type']}

🪙 <b>{p['naam']} ({p['symbool']})</b>
━━━━━━━━━━━━━━━━━━

📊 <b>LIVE MARKTDATA</b>
💰 Prijs: <b>${p['prijs']:.8f}</b>
⚡ 1u: {p['change_1h']:+.1f}% | 24u: {p['change_24h']:+.1f}% | 7d: {p['change_7d']:+.1f}%
📉 RSI: {p['rsi']} | Score: {p['score']}/12
💎 Marktwaarde: ${p['marktwaarde']:,.0f}

━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE PLAN</b>

🟢 <b>KOOP NU:</b> ${p['prijs']:.8f}
🔴 <b>STOP-LOSS (-15%):</b> ${p['sl']:.8f}
✅ <b>TP1 (+30%):</b> ${p['tp1']:.8f} → Verkoop 30%
🎯 <b>TP2 (+75%):</b> ${p['tp2']:.8f} → Verkoop 40%
🚀 <b>TP3 (+150%):</b> ${p['tp3']:.8f} → Laat lopen!

━━━━━━━━━━━━━━━━━━
⚡ <b>VROEGE SIGNALEN</b>
""" + "\n".join(p['signalen']) + """

━━━━━━━━━━━━━━━━━━
💬 Typ: analyseer """ + p['symbool'] + """ voor AI analyse
⚠️ Geen financieel advies."""

    stuur_telegram(bericht)

def dagelijkse_briefing():
    nu = datetime.now()
    if nu.hour == 7 and nu.minute < 30:
        briefing = vraag_ai("Geef mijn dagelijkse crypto briefing. Markt sentiment, Bitcoin dominantie, top kansen vandaag, wat te vermijden, en of het altseason is.")
        stuur_telegram(f"☀️ <b>DAGELIJKSE BRIEFING — {nu.strftime('%d/%m/%Y')}</b>\n\n{briefing}")

def scan_normaal():
    stuur_telegram("🔍 <b>Reguliere scanner actief</b> — Vroege signalen zoeken...")
    coins = haal_coins_op()
    gevonden = []
    for coin in coins:
        resultaat = analyseer_vroeg_signaal(coin)
        if resultaat:
            gevonden.append(resultaat)
    gevonden.sort(key=lambda x: x["score"], reverse=True)
    if gevonden:
        stuur_telegram(f"✅ <b>{len(gevonden)} vroege kansen!</b> Top 3 komen eraan...")
        time.sleep(2)
        for p in gevonden[:3]:
            stuur_signaal(p)
            time.sleep(3)
    else:
        stuur_telegram("📭 Geen vroege setups. Volgende scan over 30 minuten.")

def scan_meme():
    stuur_telegram("🎭 <b>MEME MODUS actief!</b> DexScreener scannen...")
    tokens = haal_dexscreener_trending()
    gevonden = []
    for token in tokens:
        resultaat = analyseer_meme_coin(token)
        if resultaat:
            gevonden.append(resultaat)
        time.sleep(0.5)

    if not gevonden:
        tokens2 = haal_dexscreener_nieuw()
        for token in tokens2:
            resultaat = analyseer_meme_coin(token)
            if resultaat:
                gevonden.append(resultaat)
            time.sleep(0.5)

    gevonden.sort(key=lambda x: x["score"], reverse=True)
    if gevonden:
        stuur_telegram(f"🎭 <b>{len(gevonden)} meme kansen gevonden!</b> Top 3 komen eraan...")
        for p in gevonden[:3]:
            stuur_meme_signaal(p)
            time.sleep(3)
    else:
        stuur_telegram("📭 Geen meme kansen nu. Volgende scan over 15 minuten.")

def verwerk_bericht(tekst):
    global meme_modus
    tekst_lower = tekst.lower().strip()

    if tekst_lower in ["/start", "hallo", "hoi", "hey", "hi"]:
        modus_status = "🎭 MEME MODUS AAN" if meme_modus else "📊 REGULIERE MODUS"
        stuur_telegram(f"""👋 <b>Hallo Ercan! Jouw Hedge Fund AI</b>
Status: {modus_status}

<b>COMMANDO'S:</b>

🔍 /scan — Start scan
📊 /analyseer [coin] — Analyseer coin
🎭 /mememodus aan — Meme coins aan
🎭 /mememodus uit — Meme coins uit
💼 /portfolio — Jouw portfolio
📰 /nieuws — Crypto nieuws
💡 /advies — Markt advies
⚡ /btc — Bitcoin dominantie
🌍 /exchanges — Exchange gids
📈 /insider [coin] — Smart money analyse
🎯 /dex [coin] — DexScreener analyse

<b>PORTFOLIO:</b>
koop BTC 65000 — Toevoegen
verkoop BTC — Verwijderen

Of stel gewoon een vraag! 💬""")

    elif tekst_lower == "/scan":
        if meme_modus:
            threading.Thread(target=scan_meme).start()
        else:
            threading.Thread(target=scan_normaal).start()

    elif "/mememodus aan" in tekst_lower or "meme modus aan" in tekst_lower:
        meme_modus = True
        stuur_telegram("🎭 <b>MEME MODUS INGESCHAKELD!</b>\n\nIk scan nu DexScreener voor meme coins.\nVolg grote traders: " + ", ".join(MEME_TRADERS) + "\n\nType /scan om te beginnen!")

    elif "/mememodus uit" in tekst_lower or "meme modus uit" in tekst_lower:
        meme_modus = False
        stuur_telegram("📊 <b>Terug naar reguliere modus.</b>\nIk scan nu weer normale crypto coins.")

    elif tekst_lower.startswith("/analyseer") or tekst_lower.startswith("analyseer"):
        coin = tekst.replace("/analyseer", "").replace("analyseer", "").strip()
        if coin:
            stuur_telegram(f"🔍 Analyseer {coin}...")
            antwoord = vraag_ai(f"Analyseer {coin} volledig. RSI inschatting, trend, entry, stop-loss, take profit levels, eerlijke mening. Is het verstandig nu in te stappen?", meme=meme_modus)
            stuur_telegram(f"📊 <b>Analyse {coin.upper()}</b>\n\n{antwoord}")
        else:
            stuur_telegram("Welke coin? Bijv: analyseer BTC")

    elif tekst_lower.startswith("/insider"):
        coin = tekst.replace("/insider", "").strip()
        if coin:
            stuur_telegram(f"🕵️ Smart money analyse {coin}...")
            antwoord = vraag_ai(f"Doe een smart money / insider analyse van {coin}. Kijk naar: on-chain wallet bewegingen, grote transfers, exchange inflows/outflows, developer activiteit, team wallet bewegingen, liquidity changes. Wat doet smart money met {coin}?")
            stuur_telegram(f"🕵️ <b>Smart Money: {coin.upper()}</b>\n\n{antwoord}")
        else:
            stuur_telegram("Welke coin? Bijv: /insider ETH")

    elif tekst_lower.startswith("/dex"):
        coin = tekst.replace("/dex", "").strip()
        if coin:
            stuur_telegram(f"🔍 DexScreener analyse {coin}...")
            antwoord = vraag_ai(f"Analyseer {coin} op DexScreener. Liquiditeit, volume, nieuwe listings, is het een scam of legitiem project? Wat is het advies?")
            stuur_telegram(f"📊 <b>DexScreener: {coin.upper()}</b>\n\n{antwoord}")

    elif tekst_lower == "/portfolio":
        if portfolio:
            bericht = "💼 <b>Jouw Portfolio</b>\n\n"
            for coin, data in portfolio.items():
                bericht += f"🪙 <b>{coin}</b>\nIngekocht: ${data['prijs']:.6f}\nStop-loss: ${data['sl']:.6f}\nDatum: {data['tijd']}\n\n"
            stuur_telegram(bericht)
        else:
            stuur_telegram("Portfolio leeg. Toevoegen: koop BTC 65000")

    elif tekst_lower == "/nieuws":
        stuur_telegram("📰 Nieuws ophalen...")
        antwoord = vraag_ai("Wat is het meest relevante crypto nieuws nu? Top 5 items met uitleg wat dit betekent voor de markt en jouw portfolio.")
        stuur_telegram(f"📰 <b>Crypto Nieuws</b>\n\n{antwoord}")

    elif tekst_lower == "/advies":
        antwoord = vraag_ai("Geef algemeen markt advies voor nu. Sentiment, kansen, wat vermijden, psychologie tip.")
        stuur_telegram(f"💡 <b>Markt Advies</b>\n\n{antwoord}")

    elif tekst_lower == "/btc":
        antwoord = vraag_ai("Wat is de huidige Bitcoin dominantie situatie? Is het altseason? Wat betekent dit voor altcoins en meme coins?")
        stuur_telegram(f"⚡ <b>BTC Dominantie</b>\n\n{antwoord}")

    elif tekst_lower == "/exchanges":
        antwoord = vraag_ai("Welke exchange is het beste voor welke situatie? Bitvavo, Binance, Bybit, KuCoin, Kraken, MEXC, OKX, Uniswap, PancakeSwap. Geef concrete voorbeelden wanneer je welke gebruikt.")
        stuur_telegram(f"🌍 <b>Exchange Gids</b>\n\n{antwoord}")

    elif tekst_lower.startswith("koop "):
        delen = tekst.split()
        if len(delen) >= 3:
            coin = delen[1].upper()
            try:
                prijs = float(delen[2])
                sl = round(prijs * 0.85, 8)
                portfolio[coin] = {"prijs": prijs, "sl": sl, "tijd": datetime.now().strftime("%d/%m %H:%M")}
                stuur_telegram(f"✅ <b>{coin} toegevoegd!</b>\nIngekocht: ${prijs:.6f}\nStop-loss: ${sl:.6f}\nIk waarschuw je als stop-loss nadert!")
            except:
                stuur_telegram("Gebruik: koop BTC 65000")
        else:
            stuur_telegram("Gebruik: koop BTC 65000")

    elif tekst_lower.startswith("verkoop "):
        coin = tekst.split()[1].upper() if len(tekst.split()) > 1 else ""
        if coin in portfolio:
            del portfolio[coin]
            stuur_telegram(f"✅ {coin} verwijderd uit portfolio.")
        else:
            stuur_telegram(f"{coin} staat niet in je portfolio.")

    else:
        stuur_telegram("🤔 Even nadenken...")
        antwoord = vraag_ai(tekst, meme=meme_modus)
        stuur_telegram(f"🤖 <b>Hedge Fund AI</b>\n\n{antwoord}")

def luister_telegram():
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            resp = requests.get(url, params=params, timeout=35)
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    tekst = update["message"]["text"]
                    print(f"Bericht: {tekst}")
                    verwerk_bericht(tekst)
        except Exception as e:
            print(f"Fout: {e}")
            time.sleep(5)

def main():
    stuur_telegram("""🤖 <b>HEDGE FUND AI — VOLLEDIG SYSTEEM LIVE!</b>

✅ Reguliere crypto scanner (elke 30 min)
✅ Meme coin modus via DexScreener
✅ Smart money / insider analyse
✅ Vroege signalen VOOR de stijging
✅ Alle exchanges: Bitvavo, Binance, Bybit, KuCoin, Kraken, MEXC, OKX, Uniswap, PancakeSwap
✅ AI gesprek — stel alles wat je wil
✅ Portfolio tracker
✅ Dagelijkse briefing om 8:00
✅ Take profit 1, 2, 3 + Stop-loss

Stuur /start voor alle commando's!
Eerste scan begint nu... 🚀""")

    threading.Thread(target=luister_telegram, daemon=True).start()

    scan_normaal()

    while True:
        time.sleep(30 * 60)
        dagelijkse_briefing()
        if meme_modus:
            scan_meme()
        else:
            scan_normaal()

if __name__ == "__main__":
    main()
