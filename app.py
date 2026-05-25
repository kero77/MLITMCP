"""大阪・神戸エリア 地価ダッシュボード (MLIT データプラットフォーム).

Run with:  streamlit run app.py
Requires MLIT_API_KEY in .env.local (see .env.example).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

import config
from mlit import data
from mlit.client import MlitApiError

st.set_page_config(page_title="大阪・神戸 地価ダッシュボード", layout="wide")
st.title("🏙️ 大阪・神戸エリア 地価ダッシュボード")
st.caption(
    "国土交通省データプラットフォームから地価（公示地価・地価調査）を"
    "ライブ取得し、各地点に内包された過去履歴から推移を可視化します。"
)


# --- client / key guard ------------------------------------------------------
try:
    data.get_client()
except MlitApiError as exc:
    st.error(f"APIキーが読み込めません: {exc}")
    st.info("`.env.local` に `MLIT_API_KEY=...` を設定してから再読み込みしてください。")
    st.stop()


# --- sidebar -----------------------------------------------------------------
with st.sidebar:
    st.header("表示設定")
    region_labels = {r.label: k for k, r in config.REGIONS.items()}
    selected_labels = st.multiselect(
        "都市（複数選択で比較）",
        options=list(region_labels.keys()),
        default=[config.REGIONS[config.DEFAULT_REGION].label],
    )
    region_keys = [region_labels[lbl] for lbl in selected_labels] or [config.DEFAULT_REGION]
    primary_key = region_keys[0]

    # Theme selector — only shown when more than one theme exists. Currently
    # only land_price is wired up (transaction-price needs a separate API
    # client, see config.py THEMES comment), so we hide the empty radio.
    theme_labels = {t.label: k for k, t in config.THEMES.items()}
    if len(theme_labels) > 1:
        theme_label = st.radio("テーマ", list(theme_labels.keys()))
        theme_key = theme_labels[theme_label]
    else:
        theme_key = next(iter(theme_labels.values()))


@st.cache_data(ttl=3600, show_spinner=False)
def _safe_years(region_key: str, theme_key: str) -> list[int]:
    return data.available_years(region_key, theme_key)


try:
    years = _safe_years(primary_key, theme_key)
except Exception as exc:  # noqa: BLE001 - surface any API/network issue to the UI
    st.error(f"データ取得に失敗しました: {exc}")
    st.stop()

if not years:
    st.warning("対象データが見つかりませんでした。テーマや都市を変えてお試しください。")
    st.stop()

with st.sidebar:
    # Snapshot year — single selector, defaults to the latest year that has
    # actual records. Each 地価公示 point carries its own multi-year history
    # internally, so we only fetch ONE year's worth of points and build the
    # trend chart from that.
    snapshot_year = st.selectbox(
        "スナップショット年（地点データ取得年）",
        options=years,
        index=0,
        help="この年の地点データを取得します。年次推移は各地点に内包された価格履歴(昭和58〜令和)から自動構築します。",
    )

    use_opts = []
    if theme_key == "land_price":
        try:
            use_opts = data.land_use_options(primary_key, snapshot_year)
        except Exception:  # noqa: BLE001
            use_opts = []
    use = st.selectbox("用途区分", ["（すべて）"] + use_opts)
    use = None if use == "（すべて）" else use

    trend_year_min = st.number_input(
        "推移チャート開始年",
        min_value=1983,
        max_value=snapshot_year,
        value=max(snapshot_year - 20, 1983),
        step=1,
        help="チャート横軸の表示開始年。データ自体は1983年(昭和58)まで遡れます。",
    )


# --- load trends -------------------------------------------------------------
is_land = theme_key == "land_price"
price_unit = "円/m²" if is_land else "円"

trend_frames = {}
with st.spinner("データを取得中..."):
    for key in region_keys:
        try:
            t = data.land_price_trend_embedded(key, snapshot_year, use)
            if not t.empty:
                t = t[t["year"] >= trend_year_min].reset_index(drop=True)
                # Recompute yoy after the start-year clip so the first row is NaN.
                t["yoy_pct"] = t["mean_price"].pct_change() * 100
            if not t.empty:
                trend_frames[config.REGIONS[key].label] = t
        except Exception as exc:  # noqa: BLE001
            st.warning(f"{config.REGIONS[key].label}: 取得に失敗 ({exc})")

if not trend_frames:
    st.warning("該当データがありませんでした。")
    st.stop()


# --- KPI (primary region, latest year) --------------------------------------
primary_label = config.REGIONS[primary_key].label
primary_trend = trend_frames.get(primary_label)
st.subheader(f"📊 直近の動向 — {primary_label}")
if primary_trend is not None and not primary_trend.empty:
    latest = primary_trend.iloc[-1]
    first = primary_trend.iloc[0]
    n_years = max(len(primary_trend) - 1, 1)
    cagr = ((latest["mean_price"] / first["mean_price"]) ** (1 / n_years) - 1) * 100 if first["mean_price"] else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"平均地価（{int(latest['year'])}年）", f"{latest['mean_price']:,.0f} {price_unit}")
    yoy = latest.get("yoy_pct")
    c2.metric("前年比", f"{yoy:+.1f}%" if pd.notna(yoy) else "—")
    c3.metric(f"年平均成長率(CAGR)", f"{cagr:+.1f}%")
    c4.metric("地点数", f"{int(latest['count']):,}")


# --- trend chart -------------------------------------------------------------
st.subheader("📈 年次推移")
plot_rows = []
for label, t in trend_frames.items():
    for _, row in t.iterrows():
        plot_rows.append({"年": int(row["year"]), "平均地価": row["mean_price"], "都市": label})
plot_df = pd.DataFrame(plot_rows)
fig = px.line(
    plot_df, x="年", y="平均地価", color="都市", markers=True,
    labels={"平均地価": f"平均地価 ({price_unit})"},
)
fig.update_layout(height=420, legend_title_text="")
st.plotly_chart(fig, width="stretch")

if primary_trend is not None and "yoy_pct" in primary_trend:
    yoy_df = primary_trend.dropna(subset=["yoy_pct"])
    if not yoy_df.empty:
        bar = px.bar(
            yoy_df, x="year", y="yoy_pct",
            labels={"year": "年", "yoy_pct": "前年比 (%)"},
            title=f"{primary_label} 前年比の推移",
        )
        bar.update_layout(height=320)
        st.plotly_chart(bar, width="stretch")


# --- map of detailed points (land price) -------------------------------------
if is_land:
    st.subheader(f"🗺️ 地点別の地価 — {primary_label}（{snapshot_year}年）")
    try:
        points = data.land_price_points(primary_key, snapshot_year, use)
    except Exception as exc:  # noqa: BLE001
        points = pd.DataFrame()
        st.warning(f"地点データ取得に失敗: {exc}")
    pts = points.dropna(subset=["lat", "lon", "price"]) if not points.empty else points
    if pts is not None and not pts.empty:
        pmin, pmax = pts["price"].min(), pts["price"].max()
        span = (pmax - pmin) or 1.0
        pts = pts.assign(
            _r=((pts["price"] - pmin) / span * 255).astype(int),
            _b=(255 - (pts["price"] - pmin) / span * 255).astype(int),
        )
        region = config.REGIONS[primary_key]
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=pts,
            get_position="[lon, lat]",
            get_fill_color="[_r, 60, _b, 180]",
            get_radius=120,
            pickable=True,
        )
        view = pdk.ViewState(latitude=region.center[0], longitude=region.center[1], zoom=region.zoom)
        tooltip = {"text": "{address}\n{price} 円/m²\n{use}"}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip))
        st.caption("色: 安い(青) → 高い(赤)。地点をホバーで詳細表示。")
    else:
        st.info("地点データ（緯度経度・価格）が見つかりませんでした。")


# --- data table + download ---------------------------------------------------
st.subheader("📋 データ")
table_frames = []
for label, t in trend_frames.items():
    table_frames.append(t.assign(都市=label))
table = pd.concat(table_frames, ignore_index=True)
st.dataframe(table, width="stretch")
st.download_button(
    "CSVダウンロード",
    table.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"mlit_{theme_key}_{'_'.join(region_keys)}.csv",
    mime="text/csv",
)
