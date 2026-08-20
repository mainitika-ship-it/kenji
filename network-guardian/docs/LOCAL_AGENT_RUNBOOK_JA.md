# ローカルエージェント運用指示

## 役割分担

### Agent A — router_near
ルーター/TP-Linkに近い場所。上流回線の状態を基準として取る。

### Agent B — far_room
家の中で最も通信条件が悪い部屋。Wi‑Fi伝搬の状態を見る。

### Hub
SQLiteとWebダッシュボードを持ち、A/B両方の測定を保存する。

## 各エージェントの1サイクル

1. デフォルトゲートウェイへping
2. 外部ターゲットへping
3. DNS応答時間を測定
4. 小さなHTTP応答時間を測定
5. 可能ならWi‑Fi RSSIを取得
6. SQLiteへ追記
7. Hubが設定されていればPOST
8. 3回連続badなら15秒後に再測定
9. それでもbadなら異常イベント化

## 診断の基本

- Gateway悪 / Internet悪 → `local_wifi_or_lan`
- Gateway良 / Internet悪 → `upstream_or_wan`
- Ping良 / DNS悪 → `dns`
- 自動系良 / Cloudflare Loaded悪 → `congestion_or_bufferbloat`

## 禁止

初期運用では、エージェント判断だけで以下を実行しない。

- reboot
- network interface down/up
- DNS書き換え
- router設定変更
- SIM/WAN切替

## 次Phaseで自動対処を追加する条件

最低7日間のデータを取り、誤検知率を確認してから、1対処ずつA/Bテストする。

候補順:

1. 再測定（実装済）
2. 通知のみ
3. 人が押す「WAN再接続」
4. 時間帯限定SQM
5. dual-WAN切替

各対処は、実行前値・実行後値・元に戻したかを必ずイベントとして保存する。
