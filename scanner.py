"""
Crypto Sentiment Scanner - wekelijkse X/Twitter analyse via Anthropic API
Draait elke maandag via GitHub Actions
"""

import os
import json
import datetime
import smtplib
import anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

COINS = ["Bitcoin (BTC)", "Ethereum (ETH)", "Solana (SOL)"]
HISTORY_FILE = "sentiment_history.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMAIL_FROM        = os.environ.get("EMAIL_FROM", "")
EMAIL_TO          = os.environ.get("EMAIL_TO", "")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD", "")
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))


def score_to_label(score):
    if score <= 20:  return "Extreme Fear", "🔴"
    if score <= 40:  return "Fear", "🟠"
    if score <= 60:  return "Neutraal", "⚪"
    if score <= 80:  return "Greed", "🟢"
    return "Extreme Greed", "💚"

def score_to_color(score):
    if score <= 20:  return "#E24B4A"
    if score <= 40:  return "#EF9F27"
    if score <= 60:  return "#888780"
    if score <= 80:  return "#97C459"
    return "#1D9E75"


def analyse_coin(client, coin):
    print(f"  Analyseer {coin}...")
    prompt = f"""Je bent een crypto sentiment analyst. Analyseer het actuele sentiment op X rondom {coin}.
Geef ALLEEN JSON terug:
{{
  "score": <0-100>,
  "signal": "<Extreme Fear|Fear|Neutraal|Greed|Extreme Greed>",
  "tweet_count": <getal>,
  "trend": "<Stijgend|Stabiel|Dalend>",
  "summary": "<2-3 zinnen>",
  "key_topics": ["<topic1>","<topic2>","<topic3>"]
}}"""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    text = text.replace("```json", "").replace("```", "").strip()
    s, e = text.find("{"), text.rfind("}")
    result = json.loads(text[s:e+1])
    result["coin"] = coin
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


def build_html_report(results, history):
    today = datetime.date.today().strftime("%d %B %Y")
    week  = datetime.date.today().isocalendar().week
    cards = ""
    for r in results:
        label, emoji = score_to_label(r["score"])
        color = score_to_color(r["score"])
        topics = "".join(f'<span style="background:#f0f0f0;border-radius:4px;padding:2px 8px;margin:2px;font-size:12px;display:inline-block">{t}</span>' for t in r.get("key_topics",[]))
        trend = "↑" if r["trend"]=="Stijgend" else "↓" if r["trend"]=="Dalend" else "→"
        cards += f"""<div style="background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:20px;margin-bottom:20px">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<h2 style="margin:0;font-size:18px">{emoji} {r["coin"]}</h2>
<span style="background:{color};color:#fff;padding:4px 14px;border-radius:20px;font-size:13px">{label}</span></div>
<div style="font-size:36px;font-weight:600;color:{color};margin-bottom:12px">{r["score"]}/100</div>
<p style="margin:0 0 12px;font-size:14px;color:#444;line-height:1.6">{r["summary"]}</p>
<div style="font-size:13px;color:#666;margin-bottom:10px">{trend} {r["trend"]} | ~{r["tweet_count"]:,} tweets</div>
<div>{topics}</div></div>"""

    rows = ""
    for h in reversed(history[-15:]):
        lbl, em = score_to_label(h["score"])
        c = score_to_color(h["score"])
        rows += f'<tr><td style="padding:6px 12px;font-size:13px;color:#666">{h["date"]}</td><td style="padding:6px 12px;font-size:13px">{h["coin"]}</td><td style="padding:6px 12px;text-align:center"><span style="background:{c};color:#fff;padding:2px 10px;border-radius:10px;font-size:12px">{h["score"]}</span></td><td style="padding:6px 12px;font-size:13px">{em} {lbl}</td></tr>'

    return f"""<!DOCTYPE html><html lang="nl"><head><meta charset="UTF-8"><title>Crypto Sentiment Week {week}</title></head>
<body style="margin:0;background:#f5f5f5;font-family:-apple-system,sans-serif">
<div style="max-width:600px;margin:0 auto;padding:20px">
<div style="background:#1a1a2e;border-radius:12px;padding:24px;margin-bottom:20px;color:#fff">
<div style="font-size:12px;opacity:0.6">WEEK {week}</div>
<h1 style="margin:4px 0;font-size:22px">Crypto Sentiment Scanner</h1>
<div style="font-size:13px;opacity:0.7">{today}</div></div>
{cards}
<div style="background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:20px;margin-bottom:20px">
<h3 style="margin:0 0 12px">Geschiedenis</h3>
<table style="width:100%;border-collapse:collapse">
<thead><tr style="border-bottom:1px solid #eee">
<th style="padding:6px 12px;text-align:left;font-size:12px;color:#aaa;font-weight:500">Datum</th>
<th style="padding:6px 12px;text-align:left;font-size:12px;color:#aaa;font-weight:500">Coin</th>
<th style="padding:6px 12px;font-size:12px;color:#aaa;font-weight:500">Score</th>
<th style="padding:6px 12px;text-align:left;font-size:12px;color:#aaa;font-weight:500">Signaal</th>
</tr></thead><tbody>{rows}</tbody></table></div>
<div style="text-align:center;font-size:12px;color:#aaa;padding:10px">Geen financieel advies</div>
</div></body></html>"""


def send_email(html, results):
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        with open("rapport.html","w",encoding="utf-8") as f: f.write(html)
        print("Rapport opgeslagen als rapport.html")
        return
    week = datetime.date.today().isocalendar().week
    scores = ", ".join(f"{r['coin'].split()[0]}: {r['score']}" for r in results)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Crypto Sentiment Week {week} - {scores}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html,"html","utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"E-mail verstuurd naar {EMAIL_TO}")


def main():
    print(f"Crypto Sentiment Scanner - {datetime.date.today()}")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY niet ingesteld!")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    history = load_history()
    results = []
    for coin in COINS:
        try:
            result = analyse_coin(client, coin)
            label, emoji = score_to_label(result["score"])
            print(f"  {coin}: {result['score']} {emoji} {label}")
            results.append(result)
        except Exception as e:
            print(f"  Fout bij {coin}: {e}")
    if not results:
        raise RuntimeError("Geen resultaten")
    save_history(history, results)
    html = build_html_report(results, history + results)
    send_email(html, results)
    print("Klaar!")

if __name__ == "__main__":
    main()
