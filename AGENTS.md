# Agent Notes

## Reference Paths
- /Users/nigelleong/Desktop/personal/CoPaw/src/copaw

## Environment Template Policy
- Always keep `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template` up to date.
- Any new/renamed/removed environment variable in code or docs MUST be reflected in `.env.template` in the same change.
- `.env.template` is the single source of truth for expected runtime env keys and defaults/examples.
- Do not commit secrets. Real values go in local `.env`, not in `.env.template`.
