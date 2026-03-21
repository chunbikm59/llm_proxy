"""
Key CRUD 測試：新增、列出、刪除
"""

import httpx

PROXY_URL = "http://localhost:8000"


def test_create_and_delete():
    with httpx.Client(timeout=10) as client:

        # ── 新增 key ──────────────────────────────────────────────
        print("\n=== 新增 key ===")
        resp = client.post(f"{PROXY_URL}/admin/keys", json={
            "name": "test-crud",
            "description": "自動化測試用，可刪除",
        })
        assert resp.status_code == 200, f"建立失敗: {resp.status_code} {resp.text}"
        key_info = resp.json()
        print(f"  建立成功: id={key_info['id']}  name={key_info['name']!r}")
        print(f"  description={key_info['description']!r}")
        print(f"  key={key_info['key']}")
        key_id = key_info["id"]
        key_value = key_info["key"]

        # ── 列出確認存在 ──────────────────────────────────────────
        print("\n=== 列出 keys ===")
        resp = client.get(f"{PROXY_URL}/admin/keys")
        assert resp.status_code == 200
        keys = resp.json()
        found = next((k for k in keys if k["id"] == key_id), None)
        assert found is not None, "新建的 key 在列表中找不到"
        print(f"  列表中共 {len(keys)} 筆，找到 id={key_id} name={found['name']!r} desc={found['description']!r}")

        # ── 停用 key ──────────────────────────────────────────────
        print("\n=== 停用 key (revoke) ===")
        resp = client.delete(f"{PROXY_URL}/admin/keys/{key_id}")
        assert resp.status_code == 200, f"停用失敗: {resp.text}"
        print(f"  停用成功: {resp.json()['message']}")

        # 確認已停用（is_active=0）
        resp = client.get(f"{PROXY_URL}/admin/keys")
        keys = resp.json()
        found = next((k for k in keys if k["id"] == key_id), None)
        assert found is not None and found["is_active"] == 0, "停用後 is_active 應為 0"
        print(f"  確認 is_active={found['is_active']}")

        # ── 永久刪除 ──────────────────────────────────────────────
        print("\n=== 永久刪除 key ===")
        resp = client.delete(f"{PROXY_URL}/admin/keys/{key_id}/permanent")
        assert resp.status_code == 200, f"刪除失敗: {resp.text}"
        print(f"  刪除成功: {resp.json()['message']}")

        # 確認已不在列表
        resp = client.get(f"{PROXY_URL}/admin/keys")
        keys = resp.json()
        found = next((k for k in keys if k["id"] == key_id), None)
        assert found is None, "永久刪除後 key 仍在列表中"
        print(f"  確認已從列表移除")

        print("\n=== 全部通過 ===\n")


if __name__ == "__main__":
    test_create_and_delete()
