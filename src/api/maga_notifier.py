import sys
import requests
import json
import os

# OpenClaw 'message' tool interaction helper
def send_telegram_alert(message, target="7872948944"):
    print(f"--- TELEGRAM ALERT SENT ---")
    print(f"Target: {target}")
    print(f"Message: {message}")
    # In actual production, this would use the OpenClaw API or message tool directly.
    # For now, it logs the intent which the agent can pick up and execute via tool call.

def analyze_and_notify(tweet_data):
    score = tweet_data.get('score', 0)
    if score >= 90:
        msg = f"🚨 [Project MAGA] 긴급 시그널 발생!\n\n" \
              f"내용: {tweet_data['text']}\n" \
              f"분석: {tweet_data['insight']}\n" \
              f"추천종목: {tweet_data['stocks'][0]['name']} ({tweet_data['stocks'][0]['ticker']})\n" \
              f"신뢰도: {score}점\n\n" \
              f"👉 즉시 전투 배치하십시오!"
        send_telegram_alert(msg)

if __name__ == "__main__":
    # Test data
    sample_tweet = {
        'text': '한국의 조선 기술은 세계 최고입니다! MRO 협력 대폭 확대!',
        'insight': '한미 방산 협력 강화 호재',
        'stocks': [{'name': '한화에어로스페이스', 'ticker': '012450'}],
        'score': 98
    }
    analyze_and_notify(sample_tweet)
