# Network Guardian MVP

家庭・小規模拠点の通信品質を、**検知 → 原因切り分け → 再確認 → 記録**まで行うローカル優先MVPです。

## 今回作った範囲

- 5分間隔の軽量自動監視（ping / DNS / 小さなHTTP応答）
- デフォルトゲートウェイと外部回線を分けて測定
- SQLiteへappend-onlyで保存
- 「家のWi‑Fi/LAN側」「上流回線/WAN側」「DNS」「HTTP経路」を簡易診断
- 3回連続で悪化したとき、15秒後に**再測定だけ**を自動実施
- 再測定でも悪ければ異常イベントとして記録
- Cloudflare Radar等の手動測定値（down/up/idle/loaded）をWeb画面から追加
- LAN内の別ノードから中央ノードへPOSTできる `/api/ingest`

## 安全境界

このMVPは、**自動で設定を変更しません**。

自動でしないもの:

- ルーター再起動
- Wi‑FiインターフェースON/OFF
- 2.4GHz / 5GHz変更
- DNS変更
- WAN / SIM切替
- SQM/CAKE設定変更

まず「本当に悪い状態が続いているか」と「家側か回線側か」を正しく分けることを優先します。

## すぐ試す

Python 3.11+ を想定しています（追加パッケージ不要）。

```bash
cd network-guardian
cp config.example.json config.json
python3 agent.py --once
python3 agent.py --serve
```

ブラウザ:

```text
http://127.0.0.1:8765
```

実データは `data/network_guardian.sqlite3` に保存され、Git管理対象外です。

## 2地点監視

最初に価値が高い構成は次の2台です。

1. `router_near` — TP-Link/ルーター近く
2. `far_room` — 家で最も条件が悪い部屋

遠い部屋だけ悪化 → 家のWi‑Fi側の可能性が上がる。

両方同時に悪化 → 楽天/WiMAX等の上流回線側の可能性が上がる。

### 中央ノードへ集約する場合

中央側 `config.json`:

```json
{"bind_host":"0.0.0.0","api_token":"長いランダム文字列"}
```

遠い部屋側:

```json
{
  "node_id":"far-room-node",
  "location_label":"far_room",
  "hub_url":"http://中央ノードのLAN-IP:8765",
  "api_token":"同じ長いランダム文字列"
}
```

> LAN外へ公開する場合は、この簡易HTTPサーバーを直接インターネット公開しないでください。VPN/Tailscale等または正式なHTTPS/API構成へ進めます。

## Cloudflareの今回のような値を入れる

ダッシュボードの「Cloudflare等の手動測定を追加」から、

- 下り Mbps
- 上り Mbps
- Idle latency
- Loaded latency
- 測定場所

を入力します。個人のIPアドレスは保存項目にしていません。

## 次のPhase

Phase 2では、観測データが十分集まってから以下をA/Bで追加します。

- OpenWrt SQM/CAKEの提案と前後比較
- dual-WANでの切替提案
- 明示許可後のWAN再接続
- 通知（メール/Push）
- 時間帯別ベースラインと異常検出

「自動対処」は、**測定 → 原因推定 → 影響の小さい対処 → 再測定 → 改善しなければ戻す**の閉ループでのみ許可します。
