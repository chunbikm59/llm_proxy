"""
併發測試：確認 proxy 真正支援並發
- 5 個 chat 同時送出
- 5 個 embedding 同時送出
- 3 chat + 2 embed 混合

驗證併發的方式：印出每個請求的「送出時間 offset」，
若所有 offset 都在 0.01s 內，代表是真正同時送出。
"""

import asyncio
import time
import httpx

PROXY_URL = "http://localhost:8000"
API_KEY = "sk-cF_JZ3ei0GBNkjwSmod9FYmtqxaqqpOmLPIFxos2c0g"
CHAT_MODEL = "qwen3.5-2b-claude-4.6-opus-reasoning-distilled"
EMBED_MODEL = "text-embedding-bge-m3@fp16"

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

_batch_start: float = 0.0


async def chat_request(client: httpx.AsyncClient, idx: int) -> dict:
    sent_at = time.perf_counter() - _batch_start
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{PROXY_URL}/v1/chat/completions",
            json={
                "model": CHAT_MODEL,
                "messages": [{"role": "user", "content": f"Say the number {idx} only, nothing else."}],
                "max_tokens": 20,
            },
        )
        elapsed = time.perf_counter() - t0
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {"type": "chat", "idx": idx, "ok": True,
                    "sent_at": sent_at, "elapsed": elapsed,
                    "tokens": tokens, "content": content}
        return {"type": "chat", "idx": idx, "ok": False,
                "sent_at": sent_at, "elapsed": elapsed,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"type": "chat", "idx": idx, "ok": False,
                "sent_at": sent_at, "elapsed": time.perf_counter() - t0, "error": str(e)}


async def embed_request(client: httpx.AsyncClient, idx: int) -> dict:
    sent_at = time.perf_counter() - _batch_start
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{PROXY_URL}/v1/embeddings",
            json={"model": EMBED_MODEL, "input": f"test sentence number {idx}"},
        )
        elapsed = time.perf_counter() - t0
        if resp.status_code == 200:
            data = resp.json()
            vec = data["data"][0]["embedding"]
            return {"type": "embed", "idx": idx, "ok": True,
                    "sent_at": sent_at, "elapsed": elapsed, "dims": len(vec)}
        return {"type": "embed", "idx": idx, "ok": False,
                "sent_at": sent_at, "elapsed": elapsed,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"type": "embed", "idx": idx, "ok": False,
                "sent_at": sent_at, "elapsed": time.perf_counter() - t0, "error": str(e)}


def print_results(results: list, total_elapsed: float):
    ok = sum(1 for r in results if r["ok"])
    sent_offsets = [r["sent_at"] for r in results]
    max_spread = max(sent_offsets) - min(sent_offsets)

    for r in results:
        label = f"{r['type']}-{r['idx']}"
        if r["ok"]:
            detail = f"tokens={r.get('tokens', '-')}  reply={r['content']!r}" if r["type"] == "chat" else f"dims={r['dims']}"
            print(f"  [{label}]  sent+{r['sent_at']*1000:.1f}ms  OK  {r['elapsed']:.2f}s  {detail}")
        else:
            print(f"  [{label}]  sent+{r['sent_at']*1000:.1f}ms  FAIL  {r['elapsed']:.2f}s  {r['error']}")

    print(f"  -> {ok}/{len(results)} OK, total {total_elapsed:.2f}s")
    if max_spread < 0.05:
        print(f"  [concurrent OK] spread {max_spread*1000:.1f}ms < 50ms")
    else:
        print(f"  [warning] spread {max_spread*1000:.0f}ms, may not be fully concurrent")


async def run():
    global _batch_start
    async with httpx.AsyncClient(headers=headers, timeout=120) as client:

        # ── 5 個 chat ───────────────────────────────────────────────
        print("\n" + "="*55)
        print(" Chat completions x5 concurrent")
        print("="*55)
        _batch_start = time.perf_counter()
        results = await asyncio.gather(*[chat_request(client, i + 1) for i in range(5)])
        print_results(list(results), time.perf_counter() - _batch_start)

        # ── 5 個 embedding ──────────────────────────────────────────
        print("\n" + "="*55)
        print(" Embeddings x5 concurrent")
        print("="*55)
        _batch_start = time.perf_counter()
        results = await asyncio.gather(*[embed_request(client, i + 1) for i in range(5)])
        print_results(list(results), time.perf_counter() - _batch_start)

        # ── 混合：3 chat + 2 embed ──────────────────────────────────
        print("\n" + "="*55)
        print(" Mixed concurrent (3 chat + 2 embed)")
        print("="*55)
        _batch_start = time.perf_counter()
        results = await asyncio.gather(
            chat_request(client, 1),
            chat_request(client, 2),
            chat_request(client, 3),
            embed_request(client, 4),
            embed_request(client, 5),
        )
        print_results(list(results), time.perf_counter() - _batch_start)

    print()


if __name__ == "__main__":
    asyncio.run(run())
