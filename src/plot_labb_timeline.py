#!/usr/bin/env python3
"""Render the Lab B trial from existing local records; never connect to RPC."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def records(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/labB/timeline_pressure_tool_changes.png')
    args = parser.parse_args()
    base = ROOT / 'artifacts/labB'
    pressure = records(base / 'right_pressure_remaining.jsonl')
    audit = records(base / 'right_cap_commands.jsonl')
    stamps = np.array([r['time_unix_s'] for r in pressure])
    effort = np.array([r['right_gripper_effort_Nm'] for r in pressure])
    torque = np.array([r['right_joint_torque_Nm'] for r in pressure])
    assert np.all(np.diff(stamps) > 0) and torque.shape == (len(stamps), 6)
    assert np.isfinite(effort).all() and np.isfinite(torque).all()
    origin = datetime(2026, 9, 8, 21, 39, tzinfo=JST).timestamp()

    def minute(stamp):
        return (stamp - origin) / 60

    def at(clock):
        return minute(datetime.fromisoformat('2026-09-08T' + clock + '+09:00').timestamp())

    def stamp(row):
        return datetime.fromisoformat(row['utc']).timestamp()

    fonts = {f.name for f in font_manager.fontManager.ttflist}
    jp = next((name for name in ['Noto Sans CJK JP', 'IPAexGothic', 'Droid Sans Fallback'] if name in fonts), None)
    if not jp:
        raise RuntimeError('Japanese font required for readable labels')
    plt.rcParams.update({'font.family': jp, 'font.size': 10, 'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig = plt.figure(figsize=(24, 13.5), facecolor='#f5f7fb')
    fig.text(.04, .967, 'Lab B  |  圧力の代理指標とソフトウェア・操作の変化', fontsize=23, weight='bold', color='#13263d')
    fig.text(.04, .938, '2026年9月8日・日本時間（JST）  /  右腕の試行記録  /  結果：キャップ取り外し・机上配置は未達、停止後にホーム復帰', fontsize=12, color='#37475b')
    fig.text(.04, .904, '開始前に確認済み：Piper純正グリッパ  ·  python-can / piper_sdk → effort RPC  ·  OpenCV / NumPy → キャップ検出', fontsize=11)
    fig.text(.04, .883, '上記は現行コードで確認。導入・インストール時刻やバージョン変更履歴は不明。以下のソフトウェア時刻は最初の実行記録に基づく。', fontsize=9, color='#596579')
    gs = fig.add_gridspec(4, 1, left=.072, right=.973, top=.845, bottom=.342, height_ratios=[1.4, 1.25, .9, 1.1], hspace=.19)
    axes = [fig.add_subplot(gs[i]) for i in range(4)]
    x = minute(stamps)
    end = at('22:14:35')
    gap = minute(stamps[-1])
    ticks = [at(t) for t in ['21:40:00','21:45:00','21:50:00','21:55:00','22:00:00','22:05:00','22:10:00','22:14:00']]
    for ax in axes:
        ax.set_xlim(0, end)
        ax.set_facecolor('white')
        ax.set_xticks(ticks)
        ax.grid(axis='x', color='#e3e8ef')
        ax.tick_params(axis='x', labelbottom=False)
    for ax in axes[:2]:
        ax.axvspan(gap, end, color='#dce1e8', alpha=.7)
    axes[0].plot(x, effort, color='#bc3151', lw=.75)
    axes[0].axhline(0, color='#a7afbd', lw=.6)
    axes[0].set_ylim(-1.3, .85)
    axes[0].set_ylabel('グリッパ effort\n[N·m]')
    imin = int(np.argmin(effort))
    axes[0].annotate(f'最大絶対値 {abs(effort[imin]):.3f} N·m\n{datetime.fromtimestamp(stamps[imin], JST):%H:%M:%S}（符号 {effort[imin]:.3f}）',
                     (x[imin], effort[imin]), xytext=(x[imin]-4, -.63), fontsize=9,
                     arrowprops={'arrowstyle':'->','color':'#bc3151'}, color='#942842')
    axes[0].text(end-1.55, .45, '連続ログ欠測\n22:11:44以降', ha='center', fontsize=9)
    axes[0].text(.1, .63, 'effort は圧力（Pa）ではない。接触力への換算・ゼロ点補正なし。負値は閉じ方向の反応。', fontsize=9, color='#596579')
    colors = ['#5887b5','#d29235','#56a27f','#9372ba','#dc7270','#649d9f']
    for j in range(6):
        axes[1].plot(x, torque[:, j], lw=.6, color=colors[j], alpha=.85, label=f'J{j+1}')
    axes[1].plot(x, np.max(np.abs(torque), axis=1), color='#172c46', lw=.8, label='最大絶対値')
    axes[1].set_ylabel('関節トルク\n[N·m]')
    axes[1].legend(ncol=7, loc='upper left', fontsize=8, framealpha=.85)
    # Audit timestamps mark command start, not the timestamp of the after-state.
    # Show before-state samples only, without interpolating between observations.
    observed = [(minute(stamp(r)), r['before']['gripper_open_ratio']) for r in audit
                if r.get('before') and 'gripper_open_ratio' in r['before'] and 0 <= minute(stamp(r)) <= end]
    axes[2].scatter(*np.array(observed).T, s=12, color='#217c91', label='操作開始直前の実測値')
    grips = [r for r in audit if r['command']=='grip-sweep' and 0 <= minute(stamp(r)) <= end]
    axes[2].scatter([minute(stamp(r)) for r in grips], [r['arguments']['target'] for r in grips], marker='x', s=35, color='#d0802f', label='閉開指令の最終目標')
    axes[2].set_ylim(-.05, 1.1)
    axes[2].set_ylabel('開度 [0–1]\n0=閉 / 1=開')
    axes[2].legend(loc='lower left', ncol=2, fontsize=8)
    axes[2].text(end-.1, .06, '離散観測点のみ表示（点間は未測定）', ha='right', fontsize=9, color='#596579')

    events = [
        ('21:50:20', 'A', '接触・傾き'), ('21:55:33', 'B', '挟み込み反応'),
        ('22:00:51', 'C', '分離誤認を訂正'), ('22:03:22', 'D', '空振り'),
        ('22:05:22', 'E', '再挟み込み'), ('22:07:54', 'F', '本体も追従'),
        ('22:09:39', 'G', '開放・退避'), ('22:14:00', 'H', 'ホーム指令')]
    for clock, key, label in events:
        ex = at(clock)
        for ax in axes[:3]:
            ax.axvline(ex, color='#a2abba', lw=.6, ls=':', zorder=0)
        axes[0].text(ex, 1.02, key, transform=axes[0].get_xaxis_transform(), ha='center', weight='bold', color='#37475b')

    lanes = axes[3]
    lanes.set_ylim(-.5, 2.6)
    lanes.set_yticks([0,1,2], ['操作', '制御コード', '記録'])
    spans = [
        ('21:39:32','22:11:44',2,'別プロセス RPC logger  /  約20 Hz', '#d9e9f5'),
        ('21:39:32','21:53:12',1,'NumPy・局所位置IK（使用中）', '#e3def1'),
        ('21:53:12','21:57:22',1,'手首保持', '#d0e9e4'),
        ('21:57:22','22:02:06',1,'SciPy 最適化・世界Z回転', '#efd7c6'),
        ('22:02:33','22:13:15',1,'位置IK＋手首保持', '#d0e9e4'),
        ('21:39:32','21:55:33',0,'接近・姿勢修正・接触', '#e7ecf2'),
        ('21:55:33','22:01:38',0,'挟み込み・回転・搬送試行', '#f2dce2'),
        ('22:02:33','22:05:22',0,'再位置合わせ', '#e7ecf2'),
        ('22:05:22','22:08:39',0,'直上引抜き・搬送試行', '#f2dce2'),
        ('22:08:39','22:11:44',0,'開放・再接近・停止', '#e7ecf2'),
    ]
    for start, stop, lane, label, color in spans:
        left, right = at(start), at(stop)
        lanes.barh(lane, right-left, left=left, height=.63, color=color, edgecolor='white')
        lanes.text((left+right)/2, lane, label, ha='center', va='center', fontsize=8)
    lanes.plot([at('22:14:00')], [0], 'o', color='#394e67')
    lanes.text(at('22:14:00'), .38, 'H 復帰', ha='center', fontsize=8)
    lanes.tick_params(axis='x', labelbottom=True)
    lanes.set_xticklabels(['21:40','21:45','21:50','21:55','22:00','22:05','22:10','22:14'])
    fig.text(.072, .307, '共通横軸：日本時間  /  A–H は主要イベント（下の画像と対応）。E：22:05:22 再挟み込み  /  G：22:09:39 開放後の退避。', fontsize=9, color='#596579')

    images = [
        ('20260908T125033.404242Z', 'A 21:50:33  接触で本体が傾く'),
        ('20260908T125548.174381Z', 'B 21:55:48  effort ≈ −1.05'),
        ('20260908T130051.916173Z', 'C 22:00:51  本体追従 → 分離未確認'),
        ('20260908T130333.920544Z', 'D 22:03:33  空振り ≈ −0.12'),
        ('20260908T130754.742573Z', 'F 22:07:54  再び本体が追従'),
        ('20260908T131432.721654Z', 'H 22:14:32  ホーム付近へ復帰'),
    ]
    evidence = []
    for i, (prefix, title) in enumerate(images):
        candidates = list((base/'current/2026-09-08').glob(prefix+'*/derived/head_rgb_landscape.png'))
        if len(candidates) != 1:
            raise RuntimeError(f'Ambiguous/missing image: {prefix}')
        path = candidates[0]
        ax = fig.add_axes([.04+i*.156, .105, .148, .177])
        ax.imshow(plt.imread(path))
        ax.axis('off')
        ax.set_title(title, fontsize=9, loc='left', pad=7)
        evidence.append(str(path.relative_to(ROOT)))
    fig.text(.04, .072, '読み取り：負荷増加＋開度停止は挟み込みを示すが、キャップだけを保持した証明にはならない。分離成功の発言は後の本体追従画像で否定。', fontsize=11, color='#9b3446')
    fig.text(.04, .049, '不確実性：手先Zはモデル推定。指令変位と実測変位には差がある。第6関節も指令追従不良。欠測区間を補間せず、ホーム復帰は監査・画像で確認。', fontsize=9, color='#596579')
    fig.text(.04, .029, f'出典：artifacts/labB/right_pressure_remaining.jsonl（{len(pressure):,}点） / right_cap_commands.jsonl（{len(audit)}件） / current の保存画像。元画像は加工せず使用。', fontsize=9, color='#596579')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    report = {
        'pressure_samples':len(pressure), 'audit_records':len(audit),
        'first_jst':datetime.fromtimestamp(stamps[0],JST).isoformat(),
        'last_jst':datetime.fromtimestamp(stamps[-1],JST).isoformat(),
        'median_rate_hz':float(1/np.median(np.diff(stamps))),
        'largest_sample_gap_s':float(np.max(np.diff(stamps))),
        'effort_min_Nm':float(effort.min()), 'effort_max_Nm':float(effort.max()),
        'images':evidence, 'output':str(args.output),
        'caveat':'effort is not pressure; cap removal and placement were not achieved',
    }
    args.output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
