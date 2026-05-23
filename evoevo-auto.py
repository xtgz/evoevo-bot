#!/usr/bin/env python3
import os, json, time, datetime, requests
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

API      = "https://api.evoevo.ai"
OG_RPC   = "https://evmrpc.0g.ai"
CHAIN_ID = 16661
MAX_FEE = Web3.to_wei(3, "gwei")
MAX_TIP = Web3.to_wei(2, "gwei")
IDENTITY_REGISTRY    = Web3.to_checksum_address("0x8004Ae533a0301CbD7508373b663756D26DFb028")
EVOEVO_BIND_CONTRACT = Web3.to_checksum_address("0x61bb71442749d13a4BB7257DfBFFf0452ae937f9")

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE   = os.path.join(SCRIPT_DIR, "proxy.txt")
WALLET_FILE  = os.path.join(SCRIPT_DIR, "wallets.txt")
PRIVKEY_FILE = os.path.join(SCRIPT_DIR, "privkey.txt")

for _k in ["http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","all_proxy"]:
    os.environ.pop(_k, None)

REGISTRY_ABI = [
    {
        "name": "register", "type": "function",
        "inputs": [
            {"name": "agentURI", "type": "string"},
            {"name": "metadata", "type": "tuple[]",
             "components": [{"name": "key","type": "string"},{"name": "value","type": "bytes"}]}
        ],
        "outputs": [{"name": "identityId", "type": "uint256"}],
        "stateMutability": "nonpayable"
    },
    {
        "name": "bindExistingAgent", "type": "function",
        "inputs": [
            {"name": "agentId",       "type": "uint256"},
            {"name": "evoAccount",    "type": "address"},
            {"name": "evoUserIdHash", "type": "bytes32"}
        ],
        "outputs": [], "stateMutability": "nonpayable"
    },
    {
        "name": "Transfer", "type": "event",
        "inputs": [
            {"name": "from",    "type": "address", "indexed": True},
            {"name": "to",      "type": "address", "indexed": True},
            {"name": "tokenId", "type": "uint256", "indexed": True}
        ]
    }
]

def get_w3():
    w3 = Web3(Web3.HTTPProvider(OG_RPC, request_kwargs={"timeout": 30}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect: {OG_RPC}")
    return w3

def random_fp():
    import random
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    ]
    return {"ua": random.choice(uas), "lang": "en-US,en;q=0.9"}

def load_proxies():
    if not os.path.exists(PROXY_FILE): return []
    with open(PROXY_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def evo_auth(s, addr, pk):
    r = s.post(f"{API}/v1/auth/nonce", json={"address": addr}, timeout=15)
    r.raise_for_status()
    d = r.json()
    sig = "0x" + Account.sign_message(encode_defunct(text=d["message"]), pk).signature.hex()
    r2 = s.post(f"{API}/v1/auth/login",
                json={"address": addr, "nonce": d["nonce"], "signature": sig}, timeout=15)
    r2.raise_for_status()
    return r2.json()

def get_profile(s, H):
    r = s.get(f"{API}/v1/me/profile", headers=H, timeout=10)
    r.raise_for_status()
    return r.json()

def get_points(s, H):
    r = s.get(f"{API}/v1/me/points", headers=H, timeout=10)
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

def create_agent(s, H, name):
    r = s.post(f"{API}/v1/agents", headers=H,
               json={"name": name, "agent_type": "hosted"}, timeout=15)
    return r.status_code, r.json()

def get_agents(s, H):
    r = s.get(f"{API}/v1/agents", headers=H, timeout=10)
    r.raise_for_status()
    raw = r.json()
    if isinstance(raw, list):
        return raw
    return raw.get("agents", raw.get("data", []))

def withdraw(s, H):
    r = s.post(f"{API}/v1/me/aha-moment/withdrawals", headers=H, json={}, timeout=15)
    return r.status_code, r.json()

def build_metadata(agent_id, agent_name):
    return [
        ("platform",        b"EvoEvo"),
        ("platformAgentId", agent_id.to_bytes(32, "big")),
        ("displayName",     agent_name.encode()),
        ("profileURL",      f"https://evoevo.ai/agent/detail?id={agent_id}".encode()),
    ]

def send_tx(w3, fn, addr, pk, gas=300_000):
    nonce = w3.eth.get_transaction_count(addr, "pending")
    tx = fn.build_transaction({
        "chainId": CHAIN_ID, "from": addr,
        "nonce": nonce, "gas": gas, "maxFeePerGas": MAX_FEE, "maxPriorityFeePerGas": MAX_TIP,
    })
    signed = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"    TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"    Status: {'OK' if receipt.status == 1 else 'FAILED'} | block {receipt.blockNumber}")
    return receipt, tx_hash.hex()

def extract_identity_id(w3, receipt):
    contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=REGISTRY_ABI)
    try:
        events = contract.events.Transfer().process_receipt(receipt)
        for e in events:
            if e["args"]["from"] == "0x0000000000000000000000000000000000000000":
                return int(e["args"]["tokenId"])
    except Exception:
        pass
    for log in receipt.logs:
        if log.address.lower() == IDENTITY_REGISTRY.lower() and len(log.topics) >= 4:
            return int(log.topics[3].hex(), 16)
    raise ValueError("Cannot extract identityId — check tx on chainscan.0g.ai")

def compute_hash(wallet_address):
    # evoUserIdHash = keccak256(abi.encodePacked(address))
    addr_bytes = bytes.fromhex(wallet_address.lower().replace("0x", ""))
    return Web3.keccak(addr_bytes)

def onchain_bind(w3, pk, addr, agent_id, agent_name):
    reg  = w3.eth.contract(address=IDENTITY_REGISTRY,    abi=REGISTRY_ABI)
    bind = w3.eth.contract(address=EVOEVO_BIND_CONTRACT,  abi=REGISTRY_ABI)

    print("  [TX1] register()...")
    agent_uri = f"https://metadata.evoevo.ai/agents/{agent_id}"
    metadata  = build_metadata(agent_id, agent_name)
    try:
        r1, h1 = send_tx(w3, reg.functions.register(agent_uri, metadata), addr, pk, 400_000)
        if r1.status != 1:
            print(f"  register FAILED"); return None
        print(f"  https://chainscan.0g.ai/tx/{h1}")
    except Exception as e:
        print(f"  register ERROR: {e}"); return None

    try:
        identity_id = extract_identity_id(w3, r1)
        print(f"  Identity ID: {identity_id}")
    except Exception as e:
        print(f"  {e}"); return None

    time.sleep(3)

    print("  [TX2] bindExistingAgent()...")
    uid_hash = compute_hash(addr)
    print(f"  evoUserIdHash: {uid_hash.hex()}")
    try:
        r2, h2 = send_tx(w3,
            bind.functions.bindExistingAgent(identity_id, Web3.to_checksum_address(addr), uid_hash),
            addr, pk, 200_000)
        if r2.status != 1:
            print(f"  bind FAILED"); return None
        print(f"  https://chainscan.0g.ai/tx/{h2}")
    except Exception as e:
        print(f"  bind ERROR: {e}"); return None

    return identity_id

def run_wallet(pk, invite_code, w3, proxy=None):
    acct = Account.from_key(pk)
    addr = acct.address
    fp   = random_fp()

    bal = f"{w3.from_wei(w3.eth.get_balance(addr), 'ether'):.6f}" if w3 else "?"
    print(f"\n{'='*55}")
    print(f"  Wallet : {addr}")
    print(f"  Invite : {invite_code}")
    print(f"  0G Bal : {bal} OG")
    print(f"{'='*55}")

    s = requests.Session()
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.headers.update({
        "User-Agent": fp["ua"], "Accept-Language": fp["lang"],
        "Origin": "https://evoevo.ai", "Referer": "https://evoevo.ai/",
    })

    # 1. Auth
    print("[1/7] Auth...")
    token = ""
    try:
        auth  = evo_auth(s, addr, pk)
        token = auth.get("token", "")
        print(f"  OK: {token[:40]}...")
    except Exception as e:
        print(f"  FAIL: {e}"); return None

    H = {"Authorization": f"Bearer {token}"}

    # 2. Profile
    print("[2/7] Profile...")
    my_code = ""
    try:
        profile = get_profile(s, H)
        my_code = profile.get("profile", {}).get("invite_code", "")
        print(f"  Invite code: {my_code}")
    except Exception as e:
        print(f"  FAIL: {e}")

    # 3. Redeem invite
    print("[3/7] Redeem invite...")
    if invite_code:
        try:
            sc, resp = redeem_invite(s, H, invite_code)
            print(f"  [{sc}] blindbox={resp.get('blindbox_granted', False)}")
        except Exception as e:
            print(f"  FAIL: {e}")

    # 4. Create / get agent
    print("[4/7] Agent...")
    agent_id   = None
    agent_name = f"agent-{addr[:8].lower()}"
    try:
        sc, resp = create_agent(s, H, agent_name)
        if sc == 201:
            agent_id   = resp.get("id")
            agent_name = resp.get("name", agent_name)
            print(f"  Created: {agent_name} | ID: {agent_id}")
        elif sc == 409:
            agents = get_agents(s, H)
            if agents:
                agent_id   = agents[0].get("id")
                agent_name = agents[0].get("name", agent_name)
                print(f"  Exists : {agent_name} | ID: {agent_id}")
        else:
            print(f"  [{sc}] {json.dumps(resp)[:200]}")
    except Exception as e:
        print(f"  FAIL: {e}")

    # 5. Onchain bind
    print("[5/7] Onchain Register + Bind...")
    identity_id = None
    if w3 and agent_id:
        identity_id = onchain_bind(w3, pk, addr, int(agent_id), agent_name)
        print(f"  {'Bound! id=' + str(identity_id) if identity_id else 'FAILED / skipped'}")
    else:
        print(f"  Skipped (w3={bool(w3)} agent_id={agent_id})")

    # 6. Blindboxes
    print("[6/7] Blindboxes...")
    try:
        bb      = get_blindboxes(s, H)
        pending = bb.get("assets", {}).get("pending_count", 0)
        cash    = bb.get("assets", {}).get("cash_unlocked_cents", 0)
        print(f"  Pending: {pending} | Cash: ${cash/100:.2f}")
        if pending > 0:
            sc, resp = open_blindboxes(s, H)
            print(f"  Opened [{sc}]: {json.dumps(resp)[:200]}")
    except Exception as e:
        print(f"  FAIL: {e}")

    # 7. Points + Withdraw
    print("[7/7] Points + Withdraw...")
    try:
        pts        = get_points(s, H)
        total      = pts.get("total_points", 0)
        cash_cents = pts.get("cash_cents", 0)
        print(f"  Points: {total} | Cash: ${cash_cents/100:.2f}")
        if cash_cents and cash_cents > 0:
            sc, resp = withdraw(s, H)
            print(f"  Withdraw [{sc}]: {json.dumps(resp)[:200]}")
    except Exception as e:
        print(f"  FAIL: {e}")

    result = {
        "address": addr, "private_key": pk, "token": token,
        "invite_code": invite_code, "my_code": my_code,
        "agent_id": agent_id, "identity_id": identity_id,
        "proxy": proxy or "direct",
        "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    print(f"\n  Done! Code: {my_code} | Identity: {identity_id}")
    return result

def main():
    global OG_RPC
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--invite",   default="MVJA6E75")
    p.add_argument("--wallet",   default=PRIVKEY_FILE)
    p.add_argument("--batch",    help="JSON file")
    p.add_argument("--no-proxy", action="store_true")
    p.add_argument("--rpc",      default=OG_RPC)
    args = p.parse_args()
    OG_RPC = args.rpc

    try:
        w3 = get_w3()
        print(f"0G OK | block={w3.eth.block_number} chain={w3.eth.chain_id}")
    except Exception as e:
        print(f"WARNING: 0G RPC fail ({e}) — bind skipped")
        w3 = None

    proxies = load_proxies() if not args.no_proxy else []

    if args.batch:
        with open(args.batch) as f:
            wallets = json.load(f)
    else:
        with open(args.wallet) as f:
            wallets = [{"private_key": l.strip()}
                       for l in f if l.strip() and l.startswith("0x")]

    print(f"\nWallets={len(wallets)} Proxies={len(proxies)} Invite={args.invite}")

    results = []
    for i, w in enumerate(wallets):
        pk = w.get("private_key", "")
        if not pk: continue
        proxy = proxies[i % len(proxies)] if proxies else None
        print(f"\n[Wallet {i+1}/{len(wallets)}]")
        r = run_wallet(pk, args.invite, w3, proxy)
        if r:
            results.append(r)
            with open(WALLET_FILE, "a") as f:
                f.write(json.dumps(r) + "\n")
        if i < len(wallets) - 1:
            time.sleep(3)

    ok = [r for r in results if r]
    print(f"\n{'='*55}")
    print(f"DONE: {len(ok)}/{len(wallets)}")
    for r in ok:
        bound = f"BOUND id={r['identity_id']}" if r.get("identity_id") else "NOT BOUND"
        print(f"  {r['address'][:12]}... | {r['my_code']} | {bound}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
