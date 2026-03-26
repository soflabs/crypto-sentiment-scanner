"""
BlackRock Digital Assets Intelligence Platform
Wekelijkse Crypto Sentiment & Marktanalyse
Institutioneel niveau — X/Twitter sentiment analyse
"""

import os
import json
import datetime
import smtplib
import anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

COINS = [
    {"symbol": "BTC",  "name": "Bitcoin",  "full": "Bitcoin (BTC)"},
    {"symbol": "ETH",  "name": "Ethereum", "full": "Ethereum (ETH)"},
    {"symbol": "XRP",  "name": "XRP",      "full": "XRP (XRP)"},
    {"symbol": "HBAR", "name": "Hedera",   "full": "Hedera Hashgraph (HBAR)"},
]
HISTORY_FILE = "sentiment_history.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMAIL_FROM        = os.environ.get("EMAIL_FROM", "")
EMAIL_TO          = os.environ.get("EMAIL_TO", "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD", "")
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))


def score_to_label(score):
    if score <= 15:  return "Extreme Fear",  "#C0392B"
    if score <= 30:  return "Fear",           "#E74C3C"
    if score <= 45:  return "Mild Fear",      "#E67E22"
    if score <= 55:  return "Neutraal",       "#7F8C8D"
    if score <= 70:  return "Mild Greed",     "#27AE60"
    if score <= 85:  return "Greed",          "#1D8348"
    return                   "Extreme Greed", "#145A32"


def analyse_coin(client, coin):
    print(f"  Analyseer {coin['full']}...")
    prompt = f"""Je bent een senior Digital Assets Portfolio Manager bij BlackRock met 15 jaar ervaring in institutionele crypto-investeringen. Je taak is een diepgaande, professionele wekelijkse sentimentanalyse te leveren van {coin['full']} op basis van X (Twitter) en bredere marktsentimenten.

Analyseer de volgende dimensies exhaustief:

1. SOCIAL SENTIMENT (X/Twitter)
   - Volume en toon van berichten (bullish vs bearish ratio)
   - Sentiment van key opinion leaders, whale accounts, analysts
   - Trending hashtags en narratieven
   - Community sentiment shifts t.o.v. vorige week

2. FUNDAMENTELE DRIVERS
   - Recente on-chain metrics en netwerk activiteit
   - Technologische ontwikkelingen, upgrades, partnerships
   - Institutionele adoptie signalen
   - Regulatoire ontwikkelingen (positief/negatief)

3. MACRO & MARKT CONTEXT
   - Correlatie met BTC dominantie en brede cryptomarkt
   - Impact van macro-economische factoren (rente, dollar, equities)
   - Liquiditeit en marktdiepte signalen
   - Institutionele flows en ETF/ETP activiteit indien van toepassing

4. RISICO ASSESSMENT
   - Belangrijkste downside risico's deze week
   - Catalyst events die sentiment kunnen beinvloeden
   - Technische niveaus die sentiment kunnen draaien

5. BLACKROCK INSTITUTIONEEL STANDPUNT
   - Positionering advies (overweight/neutral/underweight) met rationale
   - Tijdshorizon: 1 week outlook
   - Confidence level in de analyse

Geef je analyse UITSLUITEND als JSON terug zonder enige tekst erbuiten:
{{
  "score": <integer 0-100, fundamenteel gewogen sentiment score>,
  "signal": "<Extreme Fear|Fear|Mild Fear|Neutraal|Mild Greed|Greed|Extreme Greed>",
  "tweet_volume": "<schatting dagelijks volume, bv: 45.000+>",
  "bullish_ratio": <percentage bullish posts, integer>,
  "trend_vs_last_week": "<Sterk Stijgend|Stijgend|Stabiel|Dalend|Sterk Dalend>",
  "positioning": "<Overweight|Neutral|Underweight>",
  "confidence": <integer 1-100>,
  "executive_summary": "<2-3 zinnen scherpe institutionele samenvatting voor C-suite, met concrete data>",
  "social_analysis": "<3-4 zinnen diepgaande X/Twitter analyse met specifieke observaties>",
  "fundamental_drivers": "<3-4 zinnen over on-chain metrics, technologie en adoptie>",
  "macro_context": "<2-3 zinnen macro en markt context>",
  "key_risks": ["<risico 1>", "<risico 2>", "<risico 3>"],
  "key_catalysts": ["<catalyst 1>", "<catalyst 2>", "<catalyst 3>"],
  "blackrock_view": "<2-3 zinnen BlackRock institutioneel standpunt en positionering rationale>",
  "price_sentiment_levels": {{
    "strong_support_narrative": "<niveau of zone met uitleg>",
    "strong_resistance_narrative": "<niveau of zone met uitleg>"
  }},
  "kol_sentiment": "<Key Opinion Leaders sentiment samenvatting>",
  "institutional_signals": "<Institutionele adoptie en flow signalen>",
  "week_outlook": "<Concrete 1-week vooruitblik met scenario analyse>"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    text = text.replace("```json", "").replace("```", "").strip()
    s, e = text.find("{"), text.rfind("}")
    result = json.loads(text[s:e+1])
    result["coin"] = coin["full"]
    result["symbol"] = coin["symbol"]
    result["date"] = datetime.date.today().isoformat()
    return result


def load_history():
    if Path(HISTORY_FILE).exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history, new_entries):
    history.extend(new_entries)
    history = history[-(52 * len(COINS)):]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def score_bar(score, width=28):
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def positioning_badge(pos):
    colors = {"Overweight": "#1D8348", "Neutral": "#2C3E50", "Underweight": "#C0392B"}
    return colors.get(pos, "#2C3E50")


def build_html_report(results, history):
    today = datetime.date.today().strftime("%d %B %Y")
    week  = datetime.date.today().isocalendar().week
    year  = datetime.date.today().year

    # Portfolio summary
    avg_score = round(sum(r["score"] for r in results) / len(results))
    avg_label, avg_color = score_to_label(avg_score)
    overweight = sum(1 for r in results if r.get("positioning") == "Overweight")
    neutral    = sum(1 for r in results if r.get("positioning") == "Neutral")
    underweight= sum(1 for r in results if r.get("positioning") == "Underweight")

    cards = ""
    for r in results:
        label, color = score_to_label(r["score"])
        pos_color = positioning_badge(r.get("positioning", "Neutral"))
        bull = r.get("bullish_ratio", 50)
        bear = 100 - bull
        conf = r.get("confidence", 70)

        risks_html = "".join(f'<li style="margin:3px 0;font-size:12px;color:#555">{risk}</li>' for risk in r.get("key_risks", []))
        cats_html  = "".join(f'<li style="margin:3px 0;font-size:12px;color:#555">{cat}</li>'  for cat  in r.get("key_catalysts", []))

        cards += f"""
        <div style="background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:24px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">

          <!-- Header -->
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;border-bottom:2px solid #f0f0f0;padding-bottom:16px">
            <div>
              <div style="font-size:22px;font-weight:700;color:#1a1a2e">{r['coin']}</div>
              <div style="font-size:12px;color:#888;margin-top:2px;text-transform:uppercase;letter-spacing:0.05em">Digital Asset Intelligence Report</div>
            </div>
            <div style="text-align:right">
              <span style="background:{color};color:#fff;padding:5px 14px;border-radius:20px;font-size:13px;font-weight:600">{label}</span>
              <div style="margin-top:6px">
                <span style="background:{pos_color};color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;text-transform:uppercase">{r.get("positioning","Neutral")}</span>
              </div>
            </div>
          </div>

          <!-- Score + Gauge -->
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px">
            <div style="background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">
              <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Sentiment Score</div>
              <div style="font-size:36px;font-weight:800;color:{color}">{r['score']}</div>
              <div style="font-size:10px;color:#aaa">van 100</div>
            </div>
            <div style="background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">
              <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Bullish/Bearish</div>
              <div style="font-size:24px;font-weight:700;color:#1D8348">{bull}%</div>
              <div style="font-size:11px;color:#E74C3C">Bearish: {bear}%</div>
            </div>
            <div style="background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">
              <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Confidence</div>
              <div style="font-size:24px;font-weight:700;color:#2C3E50">{conf}%</div>
              <div style="font-size:11px;color:#888">Analyse zekerheid</div>
            </div>
          </div>

          <!-- Score bar -->
          <div style="margin-bottom:20px">
            <div style="display:flex;justify-content:space-between;font-size:10px;color:#aaa;margin-bottom:4px">
              <span>Extreme Fear (0)</span><span>Neutraal (50)</span><span>Extreme Greed (100)</span>
            </div>
            <div style="background:linear-gradient(to right,#C0392B,#E67E22,#F1C40F,#27AE60,#145A32);border-radius:4px;height:10px;position:relative">
              <div style="position:absolute;top:-4px;left:{r['score']}%;transform:translateX(-50%);width:18px;height:18px;background:#1a1a2e;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 4px rgba(0,0,0,0.3)"></div>
            </div>
          </div>

          <!-- Tweet & Trend -->
          <div style="display:flex;gap:12px;margin-bottom:20px;font-size:12px">
            <div style="background:#EBF5FB;border-radius:6px;padding:8px 14px;flex:1">
              <span style="color:#1A5276;font-weight:600">Tweet Volume:</span>
              <span style="color:#2471A3"> {r.get("tweet_volume","n/a")}/dag</span>
            </div>
            <div style="background:#EAFAF1;border-radius:6px;padding:8px 14px;flex:1">
              <span style="color:#1D6A3C;font-weight:600">Trend:</span>
              <span style="color:#1D8348"> {r.get("trend_vs_last_week","Stabiel")}</span>
            </div>
          </div>

          <!-- Executive Summary -->
          <div style="background:#1a1a2e;border-radius:8px;padding:16px;margin-bottom:16px">
            <div style="font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">Executive Summary</div>
            <div style="font-size:13px;color:#fff;line-height:1.7">{r.get("executive_summary","")}</div>
          </div>

          <!-- 2-col analysis -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
            <div style="border-left:3px solid #3498DB;padding-left:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#3498DB;margin-bottom:6px">Social Media Analyse</div>
              <div style="font-size:12px;color:#444;line-height:1.6">{r.get("social_analysis","")}</div>
            </div>
            <div style="border-left:3px solid #9B59B6;padding-left:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#9B59B6;margin-bottom:6px">Fundamentele Drivers</div>
              <div style="font-size:12px;color:#444;line-height:1.6">{r.get("fundamental_drivers","")}</div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
            <div style="border-left:3px solid #E67E22;padding-left:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#E67E22;margin-bottom:6px">Macro Context</div>
              <div style="font-size:12px;color:#444;line-height:1.6">{r.get("macro_context","")}</div>
            </div>
            <div style="border-left:3px solid #1ABC9C;padding-left:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#1ABC9C;margin-bottom:6px">KOL Sentiment</div>
              <div style="font-size:12px;color:#444;line-height:1.6">{r.get("kol_sentiment","")}</div>
            </div>
          </div>

          <!-- Risks & Catalysts -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
            <div style="background:#FDF2F2;border-radius:8px;padding:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#C0392B;margin-bottom:8px">Key Risico's</div>
              <ul style="margin:0;padding-left:16px">{risks_html}</ul>
            </div>
            <div style="background:#F0FDF4;border-radius:8px;padding:12px">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#1D6A3C;margin-bottom:8px">Key Catalysts</div>
              <ul style="margin:0;padding-left:16px">{cats_html}</ul>
            </div>
          </div>

          <!-- Institutional signals -->
          <div style="background:#F4F6F7;border-radius:8px;padding:12px;margin-bottom:12px">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#2C3E50;margin-bottom:6px">Institutionele Signalen</div>
            <div style="font-size:12px;color:#444;line-height:1.6">{r.get("institutional_signals","")}</div>
          </div>

          <!-- BlackRock View -->
          <div style="background:#1a1a2e;border:2px solid #C0A000;border-radius:8px;padding:14px">
            <div style="font-size:10px;color:#C0A000;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px">BlackRock Institutioneel Standpunt</div>
            <div style="font-size:13px;color:#fff;line-height:1.7">{r.get("blackrock_view","")}</div>
          </div>

          <!-- Week outlook -->
          <div style="margin-top:12px;border-top:1px solid #eee;padding-top:12px">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;margin-bottom:6px">1-Week Outlook</div>
            <div style="font-size:12px;color:#444;line-height:1.6">{r.get("week_outlook","")}</div>
          </div>

        </div>"""

    # History table
    hist_rows = ""
    for h in reversed(history[-20:]):
        lbl, c = score_to_label(h["score"])
        trend = h.get("trend_vs_last_week", "—")
        pos   = h.get("positioning", "—")
        hist_rows += f"""<tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:7px 10px;font-size:12px;color:#666">{h["date"]}</td>
          <td style="padding:7px 10px;font-size:12px;font-weight:600">{h.get("symbol","")}</td>
          <td style="padding:7px 10px;text-align:center"><span style="background:{c};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600">{h["score"]}</span></td>
          <td style="padding:7px 10px;font-size:11px;color:#444">{lbl}</td>
          <td style="padding:7px 10px;font-size:11px;color:#444">{trend}</td>
          <td style="padding:7px 10px;font-size:11px;color:#444">{pos}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BlackRock Digital Assets Intelligence — Week {week}/{year}</title></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif">
<div style="max-width:680px;margin:0 auto;padding:20px">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:14px;padding:28px;margin-bottom:24px;color:#fff">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div style="font-size:11px;color:#C0A000;text-transform:uppercase;letter-spacing:0.15em;margin-bottom:4px">BlackRock Digital Assets Intelligence</div>
        <div style="font-size:24px;font-weight:800;margin-bottom:4px">Crypto Sentiment Report</div>
        <div style="font-size:13px;color:#aaa">Week {week} · {today} · Institutioneel Niveau</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:#aaa;margin-bottom:4px">Portfolio Sentiment</div>
        <div style="font-size:32px;font-weight:800;color:{avg_color}">{avg_score}</div>
        <div style="font-size:12px;color:{avg_color}">{avg_label}</div>
      </div>
    </div>

    <!-- Portfolio allocation summary -->
    <div style="margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.1)">
      <div style="font-size:10px;color:#aaa;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">Positionering Overzicht</div>
      <div style="display:flex;gap:12px">
        <div style="background:rgba(29,131,72,0.3);border:1px solid #1D8348;border-radius:6px;padding:8px 16px;text-align:center">
          <div style="font-size:20px;font-weight:700;color:#27AE60">{overweight}</div>
          <div style="font-size:10px;color:#aaa">Overweight</div>
        </div>
        <div style="background:rgba(44,62,80,0.3);border:1px solid #5D6D7E;border-radius:6px;padding:8px 16px;text-align:center">
          <div style="font-size:20px;font-weight:700;color:#AEB6BF">{neutral}</div>
          <div style="font-size:10px;color:#aaa">Neutral</div>
        </div>
        <div style="background:rgba(192,57,43,0.3);border:1px solid #C0392B;border-radius:6px;padding:8px 16px;text-align:center">
          <div style="font-size:20px;font-weight:700;color:#E74C3C">{underweight}</div>
          <div style="font-size:10px;color:#aaa">Underweight</div>
        </div>
      </div>
    </div>
  </div>

  {cards}

  <!-- History -->
  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:12px;padding:20px;margin-bottom:20px">
    <div style="font-size:13px;font-weight:700;color:#1a1a2e;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.05em">Historisch Sentiment Overzicht</div>
    <table style="width:100%;border-collapse:collapse">
      <thead><tr style="background:#f8f9fa">
        <th style="padding:8px 10px;text-align:left;font-size:11px;color:#888;font-weight:600">Datum</th>
        <th style="padding:8px 10px;text-align:left;font-size:11px;color:#888;font-weight:600">Asset</th>
        <th style="padding:8px 10px;text-align:center;font-size:11px;color:#888;font-weight:600">Score</th>
        <th style="padding:8px 10px;text-align:left;font-size:11px;color:#888;font-weight:600">Signaal</th>
        <th style="padding:8px 10px;text-align:left;font-size:11px;color:#888;font-weight:600">Trend</th>
        <th style="padding:8px 10px;text-align:left;font-size:11px;color:#888;font-weight:600">Positie</th>
      </tr></thead>
      <tbody>{hist_rows}</tbody>
    </table>
  </div>

  <div style="text-align:center;font-size:10px;color:#aaa;padding:12px;line-height:1.6">
    BlackRock Digital Assets Intelligence Platform · Week {week}/{year}<br>
    Dit rapport is uitsluitend bedoeld voor institutionele beleggers. Geen financieel advies.<br>
    Gegenereerd op {today} om 08:00 CET
  </div>
</div>
</body></html>"""


def send_email(html, results):
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        with open("rapport.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Rapport opgeslagen als rapport.html")
        return

    week = datetime.date.today().isocalendar().week
    year = datetime.date.today().year
    scores = " | ".join(f"{r['symbol']}: {r['score']} ({r.get('positioning','?')})" for r in results)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BlackRock Digital Assets Intelligence — Week {week}/{year} | {scores}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"E-mail verstuurd naar {EMAIL_TO}")


def main():
    print(f"BlackRock Digital Assets Intelligence — {datetime.date.today()}")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY niet ingesteld!")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    history = load_history()
    results = []

    for coin in COINS:
        try:
            result = analyse_coin(client, coin)
            label, _ = score_to_label(result["score"])
            print(f"  {coin['symbol']}: {result['score']} — {label} | {result.get('positioning','?')}")
            results.append(result)
        except Exception as e:
            print(f"  Fout bij {coin['full']}: {e}")

    if not results:
        raise RuntimeError("Geen resultaten")

    save_history(history, results)
    html = build_html_report(results, history + results)
    send_email(html, results)
    print("Klaar!")


if __name__ == "__main__":
    main()
