# EvoEvo Bot

Auto register + invite + claim + withdraw untuk EvoEvo (evoevo.ai).  
Pure HTTP requests, no browser needed.

## Features

- Auto register wallet baru dengan invite code
- SIWE (Sign-In With Ethereum) auth
- Redeem invite code
- Create agent
- Check/open blindboxes
- Points tracking
- Cash withdrawal
- Unique fingerprint + proxy per wallet

## Setup

```bash
pip install requests eth-account

git clone https://github.com/gieskuy5/evoevo-bot.git
cd evoevo-bot
```

## Usage

```bash
# Single wallet
python3 evoevo-auto.py --invite KV7MZK85

# Batch wallets
python3 evoevo-auto.py --batch wallets.json --invite KV7MZK85

# Without proxy
python3 evoevo-auto.py --invite KV7MZK85 --no-proxy
```

## Files

```
evoevo/
├── evoevo-auto.py   # Main script
├── proxy.txt        # Proxy list
├── privkey.txt      # Private keys (git-ignored)
├── wallets.txt      # Registered data (git-ignored)
└── .gitignore
```

## API Endpoints

- `POST /v1/auth/nonce` — SIWE nonce
- `POST /v1/auth/login` — Auth (address + nonce + signature)
- `GET /v1/me/profile` — Profile + invite code
- `GET /v1/me/points` — Points breakdown
- `GET /v1/me/invite` — Blindbox/invite info
- `GET /v1/me/blindboxes` — Blindbox status
- `POST /v1/me/blindboxes/open-batch` — Open blindboxes
- `POST /v1/invites/redeem` — Redeem invite code
- `POST /v1/agents` — Create agent
- `POST /v1/me/aha-moment/withdrawals` — Withdraw cash
- `GET /v1/topics` — Prediction topics

## Rewards

- Invite friends → earn blindboxes
- Blindboxes contain: USDT, points, fragments
- Cash target: $10 (1000 cents)
- Withdraw instant when target reached

## License

MIT
