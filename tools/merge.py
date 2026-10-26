#!/usr/bin/env python3
"""各自が書き出した提出ファイル(manhole-upload-v1)を集めて、共有位置(manhole-master-v1)を作る。

使い方:
    python3 merge.py 提出ファイル1.json 提出ファイル2.json ... -o master.json

やること:
  - 番号ごとに、全員の登録位置を集める。
  - 同じ人の同じ番号が複数あれば、いちばん新しい1件だけを使う(何日も出し直しても、重く数えない)。
  - 3件以上あるときは、中央値から離れすぎた位置(既定 25m 超)を外れ値として除く。
  - 残った位置を、GPSの精度(acc)の逆二乗で重みづけして平均する。
  - 位置のばらつき(spread)が大きい番号は、確認が必要として一覧に出す。
"""
import argparse, json, math, statistics, sys
from collections import defaultdict

M_LAT = 110540.0


def m_lng(lat):
    return 111320.0 * math.cos(math.radians(lat))


def load(paths):
    rows = []  # (name, who, at, lat, lng, acc)
    for p in paths:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        if d.get('format') != 'manhole-upload-v1':
            print('スキップ(形式が違います): ' + p, file=sys.stderr)
            continue
        who = str(d.get('who') or '').strip()
        if not who:
            print('警告: 担当が空です。同じ人の出し直しを区別できません: ' + p, file=sys.stderr)
            who = '?' + p
        for s in d.get('spots', []):
            try:
                lat, lng = float(s['lat']), float(s['lng'])
            except (KeyError, TypeError, ValueError):
                continue
            if not (-90 <= lat <= 90 and -180 <= lng <= 180) or not s.get('name'):
                continue
            acc = s.get('acc')
            acc = float(acc) if isinstance(acc, (int, float)) and acc > 0 else 10.0
            at = s.get('at') or 0
            rows.append((str(s['name']).strip(), who, at, lat, lng, acc))
    return rows


def merge(rows, outlier_m, warn_m):
    by_name = defaultdict(dict)  # name -> who -> 最新の1件
    for name, who, at, lat, lng, acc in rows:
        cur = by_name[name].get(who)
        if cur is None or at >= cur[0]:
            by_name[name][who] = (at, lat, lng, acc)

    out, report = [], []
    for name in sorted(by_name):
        pts = [(lat, lng, acc) for (_, lat, lng, acc) in by_name[name].values()]
        n_all = len(pts)
        lat0 = statistics.median(p[0] for p in pts)
        lng0 = statistics.median(p[1] for p in pts)

        def off(p):
            return math.hypot((p[0] - lat0) * M_LAT, (p[1] - lng0) * m_lng(lat0))

        dropped = 0
        if n_all >= 3:
            keep = [p for p in pts if off(p) <= outlier_m]
            dropped = n_all - len(keep)
            if keep:
                pts = keep
        w = [1.0 / (p[2] ** 2) for p in pts]
        lat = sum(wi * p[0] for wi, p in zip(w, pts)) / sum(w)
        lng = sum(wi * p[1] for wi, p in zip(w, pts)) / sum(w)
        spread = max(math.hypot((p[0] - lat) * M_LAT, (p[1] - lng) * m_lng(lat)) for p in pts)
        out.append({'name': name, 'lat': round(lat, 7), 'lng': round(lng, 7), 'n': len(pts), 'spread': round(spread, 1)})
        if spread > warn_m or n_all == 1 or dropped:
            why = []
            if n_all == 1:
                why.append('登録が1人分だけ')
            if dropped:
                why.append('外れ値 %d 件を除外' % dropped)
            if spread > warn_m:
                why.append('ばらつき %.0f m' % spread)
            report.append('  %-12s %s' % (name, ' / '.join(why)))
    return out, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+')
    ap.add_argument('-o', '--out', default='master.json')
    ap.add_argument('--outlier', type=float, default=25.0, help='外れ値とみなす距離(m)')
    ap.add_argument('--warn', type=float, default=15.0, help='確認が必要とするばらつき(m)')
    a = ap.parse_args()
    rows = load(a.files)
    spots, report = merge(rows, a.outlier, a.warn)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'format': 'manhole-master-v1', 'spots': spots}, f, ensure_ascii=False, indent=2)
    print('%d 件の番号を %s に書き出しました(入力 %d 件)。' % (len(spots), a.out, len(rows)))
    if report:
        print('確認が必要な番号:')
        print('\n'.join(report))


if __name__ == '__main__':
    main()
