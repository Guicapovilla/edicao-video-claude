import json
from datetime import datetime, timedelta, date as _date


def _q2_start(hoje):
    q_start_month = ((hoje.month - 1) // 3) * 3 + 1
    return _date(hoje.year, q_start_month, 1)


def _analytics_period_totals(analytics, channel_id: str, start: _date, end: _date):
    rows = (
        analytics.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=str(start),
            endDate=str(end),
            metrics="views,estimatedMinutesWatched,subscribersGained,estimatedRevenue",
        )
        .execute()
        .get("rows")
        or []
    )
    if not rows:
        return 0, 0.0, 0, 0.0
    r = rows[0]
    return int(r[0] or 0), float(r[1] or 0), int(r[2] or 0), float(r[3] or 0)


def _analytics_daily_views(analytics, channel_id: str, start: _date, end: _date):
    rows = (
        analytics.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=str(start),
            endDate=str(end),
            metrics="views",
            dimensions="day",
            sort="day",
        )
        .execute()
        .get("rows")
        or []
    )
    return [(str(row[0]), int(row[1] or 0)) for row in rows]


def _linhas_resumo_7_vs_7(analytics, cid, usd: float, hoje: _date):
    """Últimos 7 dias (inclusive hoje) vs. os 7 dias anteriores, + série diária de views."""
    start_cur = hoje - timedelta(days=6)
    end_ant = hoje - timedelta(days=7)
    start_ant = hoje - timedelta(days=13)

    try:
        v_cur, min_cur, sub_cur, rev_cur_usd = _analytics_period_totals(analytics, cid, start_cur, end_cur)
        v_ant, min_ant, sub_ant, rev_ant_usd = _analytics_period_totals(analytics, cid, start_ant, end_ant)
    except Exception:
        z = "O mesmo de 7 dias atrás"
        return [
            "",
            "=== RESUMO ANALYTICS 7D vs 7D ===",
            "r7_views_atual: 0",
            "r7_views_ant: 0",
            "r7_minutos_atual: 0",
            "r7_minutos_ant: 0",
            "r7_inscritos_atual: 0",
            "r7_inscritos_ant: 0",
            "r7_receita_brl_atual: 0.00",
            "r7_receita_brl_ant: 0.00",
            "r7_horas_atual: 0.0",
            "r7_horas_ant: 0.0",
            f"r7_msg_views: {z}",
            f"r7_msg_horas: {z}",
            f"r7_msg_inscritos: {z}",
            f"r7_msg_receita: {z}",
            "r7_series_views_json: []",
            "",
        ]

    serie = []
    try:
        serie = _analytics_daily_views(analytics, cid, start_cur, end_cur)
    except Exception:
        serie = []

    def _pct_msg(cur_num: float, prev_num: float) -> str:
        if prev_num == 0 and cur_num == 0:
            return "Sem dados nos dois períodos"
        if prev_num == 0:
            return "Comparação indisponível (período anterior zerado)"
        delta = (cur_num - prev_num) / prev_num * 100
        arred = round(abs(delta))
        if arred == 0:
            return "O mesmo de 7 dias atrás"
        if delta > 0:
            return f"{arred}% a mais do que há 7 dias"
        return f"{arred}% a menos do que há 7 dias"

    horas_cur = min_cur / 60.0
    horas_ant = min_ant / 60.0

    msg_views = _pct_msg(float(v_cur), float(v_ant))
    msg_horas = _pct_msg(horas_cur, horas_ant)
    msg_subs = _pct_msg(float(sub_cur), float(sub_ant))
    msg_rev = _pct_msg(rev_cur_usd * usd, rev_ant_usd * usd)

    series_payload = [{"d": d, "v": v} for d, v in serie]

    return [
        "",
        "=== RESUMO ANALYTICS 7D vs 7D ===",
        f"r7_views_atual: {v_cur}",
        f"r7_views_ant: {v_ant}",
        f"r7_minutos_atual: {round(min_cur)}",
        f"r7_minutos_ant: {round(min_ant)}",
        f"r7_inscritos_atual: {sub_cur}",
        f"r7_inscritos_ant: {sub_ant}",
        f"r7_receita_brl_atual: {rev_cur_usd * usd:.2f}",
        f"r7_receita_brl_ant: {rev_ant_usd * usd:.2f}",
        f"r7_horas_atual: {horas_cur:.2f}",
        f"r7_horas_ant: {horas_ant:.2f}",
        f"r7_msg_views: {msg_views}",
        f"r7_msg_horas: {msg_horas}",
        f"r7_msg_inscritos: {msg_subs}",
        f"r7_msg_receita: {msg_rev}",
        f"r7_series_views_json: {json.dumps(series_payload, ensure_ascii=False)}",
        "",
    ]


def coletar_canal(youtube, analytics, usd):
    hoje  = datetime.now().date()
    start = hoje - timedelta(days=28)

    ch   = youtube.channels().list(part='snippet,statistics', mine=True).execute()['items'][0]
    cid  = ch['id']
    stat = ch['statistics']

    an = analytics.reports().query(
        ids=f'channel=={cid}',
        startDate=str(start), endDate=str(hoje),
        metrics='views,estimatedMinutesWatched,subscribersGained,estimatedRevenue,cpm',
        dimensions='day', sort='day'
    ).execute()

    total_views = total_min = total_subs = total_rev = 0
    dias = []
    for r in (an.get('rows') or []):
        total_views += int(r[1])
        total_min   += int(r[2])
        total_subs  += int(r[3])
        total_rev   += float(r[4])
        dias.append(f"{r[0]} | Views: {int(r[1])} | BRL: R${float(r[4])*usd:.2f} | CPM: ${float(r[5]):.2f}")

    # Receita Q2: se o início do trimestre está fora da janela de 28 dias, faz query adicional
    q2_start = _q2_start(hoje)
    if q2_start < start:
        an_q2 = analytics.reports().query(
            ids=f'channel=={cid}',
            startDate=str(q2_start), endDate=str(hoje),
            metrics='estimatedRevenue',
        ).execute()
        receita_q2_brl = sum(float(r[0]) for r in (an_q2.get('rows') or [])) * usd
    else:
        receita_q2_brl = total_rev * usd

    ids_recentes = [i['id']['videoId'] for i in youtube.search().list(
        part='snippet', forMine=True, type='video', order='date', maxResults=15
    ).execute()['items']]

    ids_top = [i['id']['videoId'] for i in youtube.search().list(
        part='snippet', forMine=True, type='video', order='viewCount', maxResults=20
    ).execute()['items']]

    todos_ids = ids_recentes + [i for i in ids_top if i not in ids_recentes]
    todos_ids = todos_ids[:25]

    vstats = youtube.videos().list(part='statistics,snippet', id=','.join(todos_ids)).execute()
    videos_list = sorted(vstats['items'], key=lambda v: int(v['statistics'].get('viewCount', 0)), reverse=True)

    top_views = []
    for i, v in enumerate(videos_list, 1):
        s = v['statistics']
        pub = v['snippet'].get('publishedAt', '')[:10]
        top_views.append(
            f"{i}. {v['snippet']['title']} | "
            f"Views: {s.get('viewCount',0)} | "
            f"Likes: {s.get('likeCount',0)} | "
            f"Comentarios: {s.get('commentCount',0)} | "
            f"Publicado: {pub}"
        )

    rv = analytics.reports().query(
        ids=f'channel=={cid}', startDate='2020-01-01', endDate=str(hoje),
        metrics='estimatedRevenue,views', dimensions='video',
        sort='-estimatedRevenue', maxResults=25
    ).execute()

    rv_ids = ','.join([r[0] for r in (rv.get('rows') or [])])
    titulos = {}
    if rv_ids:
        for v in youtube.videos().list(part='snippet', id=rv_ids).execute()['items']:
            titulos[v['id']] = v['snippet']['title']

    top_receita = []
    receita_por_video = {}
    for i, r in enumerate((rv.get('rows') or []), 1):
        titulo = titulos.get(r[0], r[0])
        brl = float(r[1]) * usd
        views = int(r[2])
        rpm = (brl / views * 1000) if views > 0 else 0
        top_receita.append(f"{i}. {titulo} | BRL: R${brl:.2f} | Views: {views} | RPM: R${rpm:.2f}")
        receita_por_video[r[0]] = {'titulo': titulo, 'brl': brl, 'views': views, 'rpm': rpm}

    linhas = [
        '=== DADOS DO CANAL ===',
        f"Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Canal: {ch['snippet']['title']}",
        f"Inscritos: {stat['subscriberCount']}",
        f"Views totais: {stat['viewCount']}",
        f"Total de videos: {stat['videoCount']}",
        f"Cotacao USD/BRL: {usd:.6f}",
        '',
        '=== ANALYTICS 28 DIAS ===',
        f"Views totais: {total_views}",
        f"Horas assistidas: {round(total_min/60)}",
        f"Novos inscritos: {total_subs}",
        f"Receita total (BRL): R$ {total_rev*usd:.2f}",
        '',
        *_linhas_resumo_7_vs_7(analytics, cid, usd, hoje),
        '=== TOP 10 VIDEOS POR VIEWS ===',
        *top_views[:10],
        '',
        '=== TOP 10 VIDEOS POR RECEITA ===',
        *top_receita[:10],
        '',
        '=== RECEITA DIARIA (ultimos 28 dias) ===',
        *dias,
    ]
    return '\n'.join(linhas), receita_por_video, receita_q2_brl
