#!/usr/bin/env python3
"""
EvoEvo Auto Register + Invite + Claim + Withdraw
Pure HTTP requests, no browser needed.

Usage:
  python3 evoevo-auto.py                        # Main wallet
  python3 evoevo-auto.py --invite KV7MZK85      # With invite code
  python3 evoevo-auto.py --batch wallets.json    # Batch wallets
"""
import os, json, time, datetime, requests, sys, uuid
from eth_account import Account
from eth_account.messages import encode_defunct

API = "https://api.evoevo.ai"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(SCRIPT_DIR, "proxy.txt")
WALLET_FILE = os.path.join(SCRIPT_DIR, "wallets.txt")
PRIVKEY_FILE = os.path.join(SCRIPT_DIR, "privkey.txt")

# Clear proxy env
for _k in ["http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","all_proxy"]:
    os.environ.pop(_k, None)

# ============ FINGERPRINT ============
def random_fp():
    import random
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    ]
    langs = ["en-US,en;q=0.9","en-US,en;q=0.9,id;q=0.8","en-GB,en;q=0.9"]
    return {"ua": random.choice(uas), "lang": random.choice(langs)}

# ============ PROXY ============
def load_proxies():
    if not os.path.exists(PROXY_FILE): return []
    with open(PROXY_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

# ============ AUTH ============
def evo_auth(s, addr, pk):
    """Full EvoEvo SIWE auth"""
    r = s.post(f"{API}/v1/auth/nonce", json={"address": addr}, timeout=15)
    r.raise_for_status()
    d = r.json()
    msg = d["message"]
    nonce = d["nonce"]
    
    sig = "0x" + Account.sign_message(encode_defunct(text=msg), pk).signature.hex()
    
    r2 = s.post(f"{API}/v1/auth/login", json={"address": addr, "nonce": nonce, "signature": sig}, timeout=15)
    r2.raise_for_status()
    return r2.json()

# ============ API CALLS ============
def get_profile(s, H):
    r = s.get(f"{API}/v1/me/profile", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def get_points(s, H):
    r = s.get(f"{API}/v1/me/points", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def get_invite(s, H):
    r = s.get(f"{API}/v1/me/invite", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def get_blindboxes(s, H):
    r = s.get(f"{API}/v1/me/blindboxes", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def open_blindboxes(s, H):
    r = s.post(f"{API}/v1/me/blindboxes/open-batch", headers=H, json={}, timeout=15)
    return r.status_code, r.json()

def redeem_invite(s, H, code):
    r = s.post(f"{API}/v1/invites/redeem", headers=H, json={"invite_code": code}, timeout=15)
    return r.status_code, r.json()

def create_agent(s, H, name, agent_type="hosted"):
    r = s.post(f"{API}/v1/agents", headers=H, json={"name": name, "agent_type": agent_type}, timeout=15)
    return r.status_code, r.json()

def withdraw(s, H):
    r = s.post(f"{API}/v1/me/aha-moment/withdrawals", headers=H, json={}, timeout=15)
    return r.status_code, r.json()

def get_topics(s, H):
    r = s.get(f"{API}/v1/topics", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def submit_opinion(s, H, topic_id, side, reasoning=""):
    r = s.post(f"{API}/v1/opinions", headers=H, json={
        "topic_id": topic_id, "side": side, "reasoning": reasoning
    }, timeout=15)
    return r.status_code, r.json()

# ============ MAIN FLOW ============
def register_and_claim(pk, invite_code, proxy=None):
    acct = Account.from_key(pk)
    addr = acct.address
    fp = random_fp()
    
    print(f"\n{'='*50}")
    print(f"  Wallet: {addr}")
    print(f"  Invite: {invite_code}")
    print(f"{'='*50}")
    
    s = requests.Session()
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.headers.update({
        "User-Agent": fp["ua"],
        "Accept-Language": fp["lang"],
        "Origin": "https://evoevo.ai",
        "Referer": "https://evoevo.ai/",
    })
    
    # 1. Auth
    print("[1/6] Auth...")
    try:
        auth = evo_auth(s, addr, pk)
        token = auth.get("token", "")
        expires = auth.get("expires_at", "")
        print(f"  Token: {token[:40]}...")
        print(f"  Expires: {expires}")
    except Exception as e:
        print(f"  FAIL: {e}")
        # Retry without proxy
        if proxy:
            s.proxies = {}
            try:
                auth = evo_auth(s, addr, pk)
                token = auth.get("token", "")
                print(f"  OK (direct): {token[:40]}...")
            except Exception as e2:
                print(f"  FAIL (direct): {e2}")
                return None
        else:
            return None
    
    H = {"Authorization": f"Bearer {token}"}
    
    # 2. Profile
    print("[2/6] Profile...")
    try:
        profile = get_profile(s, H)
        my_code = profile.get("profile", {}).get("invite_code", "")
        print(f"  My invite code: {my_code}")
    except Exception as e:
        print(f"  FAIL: {e}")
    
    # 3. Redeem invite code
    print("[3/6] Redeem invite...")
    if invite_code:
        try:
            sc, resp = redeem_invite(s, H, invite_code)
            print(f"  [{sc}] Status: {resp.get('qualification_status', '')}")
            print(f"  Blindbox granted: {resp.get('blindbox_granted', False)}")
            inviter = resp.get("inviter_wallet", "")[:10]
            print(f"  Inviter: {inviter}...")
        except Exception as e:
            print(f"  FAIL: {e}")
    
    # 4. Create agent (qualifies for rewards)
    print("[4/6] Create agent...")
    try:
        agent_name = f"agent-{addr[:8]}"
        sc, resp = create_agent(s, H, agent_name)
        if sc == 201:
            print(f"  Created: {resp.get('name', agent_name)}")
        else:
            print(f"  [{sc}] {json.dumps(resp)[:200]}")
    except Exception as e:
        print(f"  FAIL: {e}")
    
    # 5. Blindboxes
    print("[5/6] Blindboxes...")
    try:
        bb = get_blindboxes(s, H)
        total = bb.get("assets", {}).get("total_count", 0)
        pending = bb.get("assets", {}).get("pending_count", 0)
        opened = bb.get("assets", {}).get("opened_count", 0)
        cash = bb.get("assets", {}).get("cash_unlocked_cents", 0)
        print(f"  Total: {total} | Pending: {pending} | Opened: {opened}")
        print(f"  Cash unlocked: ${cash/100:.2f}")
        
        if pending > 0:
            sc, resp = open_blindboxes(s, H)
            print(f"  Opened [{sc}]: {json.dumps(resp)[:300]}")
        else:
            print(f"  No pending boxes to open")
    except Exception as e:
        print(f"  FAIL: {e}")
    
    # 6. Points + Withdraw
    print("[6/6] Points + Withdraw...")
    try:
        pts = get_points(s, H)
        total = pts.get("total_points", 0)
        claimable = pts.get("claimable_points", 0)
        cash_cents = pts.get("cash_cents", 0)
        print(f"  Points: {total} | Claimable: {claimable}")
        print(f"  Cash: ${cash_cents/100:.2f}" if cash_cents else "  Cash: $0.00")
        
        # Try withdraw
        if cash_cents and cash_cents > 0:
            sc, resp = withdraw(s, H)
            print(f"  Withdraw [{sc}]: {json.dumps(resp)[:200]}")
    except Exception as e:
        print(f"  FAIL: {e}")
    
    result = {
        "address": addr,
        "private_key": pk,
        "token": token,
        "invite_code": invite_code,
        "my_code": profile.get("profile", {}).get("invite_code", ""),
        "proxy": proxy or "direct",
        "ua": fp["ua"][:60],
        "registered_at": datetime.datetime.utcnow().isoformat(),
    }
    print(f"\n  OK! My code: {result['my_code']}")
    return result

# ============ CLI ============
def main():
    import argparse
    p = argparse.ArgumentParser(description="EvoEvo Auto Register + Claim")
    p.add_argument("--invite", default="KV7MZK85", help="Invite code")
    p.add_argument("--wallet", default=PRIVKEY_FILE, help="Wallet file")
    p.add_argument("--batch", help="Batch wallets JSON file")
    p.add_argument("--no-proxy", action="store_true")
    args = p.parse_args()
    
    proxies = load_proxies() if not args.no_proxy else []
    
    if args.batch:
        with open(args.batch) as f:
            wallets = json.load(f)
    else:
        with open(args.wallet) as f:
            wallets = [{"private_key": l.strip()} for l in f if l.strip() and l.startswith("0x")]
    
    print(f"{'='*50}")
    print(f"  EvoEvo Auto Register")
    print(f"  Invite: {args.invite}")
    print(f"  Wallets: {len(wallets)}")
    print(f"  Proxies: {len(proxies)}")
    print(f"{'='*50}")
    
    used_proxies = set()
    results = []
    
    for i, w in enumerate(wallets):
        pk = w.get("private_key", "")
        if not pk: continue
        
        proxy = None
        if proxies:
            avail = [p for p in proxies if p not in used_proxies]
            if not avail: avail = proxies
            proxy = avail[i % len(avail)]
            used_proxies.add(proxy)
        
        print(f"\n[{i+1}/{len(wallets)}]")
        r = register_and_claim(pk, args.invite, proxy)
        if r:
            results.append(r)
            # Save to file
            with open(WALLET_FILE, "a") as f:
                f.write(json.dumps(r) + "\n")
        
        if i < len(wallets) - 1:
            time.sleep(2)
    
    ok = [r for r in results if r]
    print(f"\n{'='*50}")
    print(f"  DONE: {len(ok)}/{len(wallets)}")
    for r in ok:
        print(f"  {r['address'][:10]}... Code: {r['my_code']}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
