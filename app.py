# =====================================================================
# BAGIAN 1 : IMPORT LIBRARY
# =====================================================================
from concurrent.futures import ThreadPoolExecutor   # Pengambilan halaman paralel
from urllib.parse import urljoin, urlparse, urldefrag

import requests                                     # Mengambil isi halaman web
import networkx as nx                               # Membentuk graph & hitung PageRank
import pandas as pd                                 # Tabel Top 10
import streamlit as st                              # Tampilan aplikasi
import streamlit.components.v1 as components        # Menampilkan HTML graph
from bs4 import BeautifulSoup                       # Parsing HTML untuk ambil link
from pyvis.network import Network                   # Graph interaktif


# =====================================================================
# BAGIAN 2 : PENGATURAN HALAMAN STREAMLIT
# (harus dipanggil sebelum perintah st. lainnya)
# =====================================================================
st.set_page_config(layout="wide")   # Halaman selebar layar agar graph lebih besar


# =====================================================================
# BAGIAN 3 : KONSTANTA & PENGATURAN
# =====================================================================
# Ekstensi file yang dilewati saat crawling (bukan halaman web)
SKIP = (".jpg", ".png", ".gif", ".pdf", ".zip", ".docx")

# Warna khusus untuk node dengan PageRank peringkat 1
WARNA_RANK1 = "#00c853"   # Hijau terang

# Warna node berdasarkan kedalaman (depth)
WARNA_DEPTH = {
    0: "#e4572e",   # Merah   : halaman awal
    1: "#f4b942",   # Kuning  : depth 1
    2: "#76b5c5",   # Biru    : depth 2
    3: "#9b8bd5",   # Ungu    : depth 3
}

# Ukuran kotak graph (TINGGI_KOTAK harus ~20px lebih besar dari TINGGI_GRAPH)
TINGGI_GRAPH = 900   # Tinggi graph di dalam kotak (px)
TINGGI_KOTAK = 920   # Tinggi kotak penampung di Streamlit (px)

# Jumlah halaman yang diambil bersamaan saat crawling
JUMLAH_THREAD = 20


# =====================================================================
# BAGIAN 4 : FUNGSI MENGAMBIL HTML SATU HALAMAN
# =====================================================================
def ambil_html(url):
    """Mengambil HTML satu halaman (dipanggil paralel). None jika gagal."""
    try:
        r = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        # Lewati jika bukan halaman HTML
        if "text/html" not in r.headers.get("Content-Type", ""):
            return None

        return r.text
    except Exception:
        return None


# =====================================================================
# BAGIAN 5 : FUNGSI CRAWLING (BFS PER LEVEL, TANPA BATAS HALAMAN)
# =====================================================================
def crawl(seed, max_depth):
    """BFS per level dengan pengambilan halaman paralel, tanpa batas halaman.

    Halaman pada kedalaman maksimal tidak perlu dibuka, karena link di
    dalamnya tidak dicatat. Node-nya tetap muncul lewat edge dari level
    sebelumnya.

    Mengembalikan: (daftar edge, jumlah halaman dibuka, kedalaman tiap halaman)
    """

    visited = {seed}          # Halaman yang sudah ditemukan
    edges = []                # Hubungan antar halaman (asal, tujuan)
    depth_pages = {seed: 0}   # Kedalaman setiap halaman
    dibuka = 0                # Jumlah halaman yang berhasil dibuka
    level = [seed]            # Halaman pada level yang sedang diproses

    for depth in range(max_depth):
        if not level:
            break

        # Ambil seluruh halaman pada level ini secara paralel
        with ThreadPoolExecutor(max_workers=JUMLAH_THREAD) as ex:
            hasil = list(ex.map(ambil_html, level))

        berikutnya = []   # Halaman baru untuk level selanjutnya

        for url, html in zip(level, hasil):
            if html is None:
                continue

            dibuka += 1

            # Ambil semua link di dalam halaman
            for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
                link = urldefrag(urljoin(url, a["href"]))[0].rstrip("/")

                # Abaikan link yang tidak valid / file non-halaman
                if (
                    not link.startswith("http")
                    or link == url
                    or link.lower().endswith(SKIP)
                ):
                    continue

                # Simpan hubungan antar halaman
                edges.append((url, link))

                # Masukkan halaman baru jika belum pernah ditemukan
                if link not in visited:
                    visited.add(link)
                    depth_pages[link] = depth + 1
                    berikutnya.append(link)

        level = berikutnya

    return edges, dibuka, depth_pages


# =====================================================================
# BAGIAN 6 : FUNGSI MEMBUAT GRAPH INTERAKTIF
# =====================================================================
def graph_interaktif(G, pr, depth_pages):
    """Graph berwarna berdasarkan depth; node PageRank #1 diberi warna khusus."""

    # Urutan halaman dari PageRank tertinggi ke terendah
    urut = sorted(pr, key=pr.get, reverse=True)
    top10 = urut[:10]    # 10 node teratas (diberi label)
    rank1 = urut[0]      # Node peringkat 1

    # Menampilkan seluruh node & edge hasil crawling (tanpa dipotong)
    sub = G

    # ---------- Membuat objek graph ----------
    net = Network(
        height=f"{TINGGI_GRAPH}px",
        width="100%",
        directed=True,
        cdn_resources="in_line"
    )

    # ---------- Menambahkan node ----------
    for n in sub.nodes():
        p = urlparse(n)
        d = depth_pages.get(n, -1)
        is_rank1 = n == rank1

        # Rank 1 -> warna khusus, selain itu berdasarkan kedalaman
        warna = WARNA_RANK1 if is_rank1 else WARNA_DEPTH.get(d, "#808080")

        # Isi tooltip saat hover / klik
        judul = (
            f"{'<b>PERINGKAT 1 PAGERANK</b><br>' if is_rank1 else ''}"
            f"URL: {n}<br>"
            f"Kedalaman: {d}<br>"
            f"PageRank: {pr[n]:.5f}"
        )

        # Label: rank 1 diberi bintang, top 10 diberi nama, lainnya kosong
        if is_rank1:
            label = "★ " + p.netloc + p.path[:15]
        elif n in top10:
            label = p.netloc + p.path[:15]
        else:
            label = " "

        net.add_node(
            n,
            label=label,
            title=judul,
            size=10 + pr[n] * 600,
            color={
                "background": warna,
                "border": "#1b5e20" if is_rank1 else warna,
            },
            borderWidth=4 if is_rank1 else 1,
            font={"size": 18, "bold": True} if is_rank1 else {"size": 14},
        )

    # ---------- Menambahkan edge ----------
    for a, b in sub.edges():
        net.add_edge(a, b)

    # ---------- Pengaturan physics & interaksi ----------
    net.set_options("""{
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -6000,
          "springLength": 150,
          "damping": 0.6,
          "avoidOverlap": 0.5
        },
        "stabilization": {"iterations": 100, "updateInterval": 50}
      },
      "interaction": {
        "hover": true,
        "dragNodes": true,
        "zoomView": true
      },
      "edges": {"smooth": false}
    }""")

    html = net.generate_html()

    # Mematikan physics setelah graph stabil
    html = html.replace(
        "return network;",
        'network.once("stabilizationIterationsDone", function () { '
        'network.setOptions({physics: false}); });\n return network;'
    )

    return html


# =====================================================================
# BAGIAN 7 : TAMPILAN UTAMA - INPUT PENGGUNA
# =====================================================================
st.title("Web Crawler & PageRank")

seed = st.text_input(
    "Link awal",
    "https://www.trunojoyo.ac.id"
)

depth = st.number_input(
    "Kedalaman",
    1,   # minimal
    3,   # maksimal
    2    # bawaan
)


# =====================================================================
# BAGIAN 8 : PROSES SAAT TOMBOL DITEKAN
# =====================================================================
if st.button("Mulai Crawling"):

    # ---------- 8a. Crawling ----------
    with st.spinner("Sedang crawling (tanpa batas halaman, mohon tunggu)..."):
        edges, dibuka, depth_pages = crawl(seed.rstrip("/"), depth)

    if not edges:
        st.error("Tidak ada link ditemukan. Coba link lain.")
        st.stop()

    # ---------- 8b. Membentuk graph & menghitung PageRank ----------
    G = nx.DiGraph(edges)
    nx.set_node_attributes(G, depth_pages, "depth")   # Simpan kedalaman di node

    pr = nx.pagerank(G, alpha=0.85)
    rank1 = max(pr, key=pr.get)

    # ---------- 8c. Metrik ringkasan ----------
    m1, m2, m3 = st.columns(3)

    m1.metric("Halaman dibuka", dibuka)
    m2.metric("Jumlah node (halaman)", G.number_of_nodes())
    m3.metric("Jumlah edge (hubungan)", G.number_of_edges())

    st.success(f"PageRank peringkat 1: {rank1} ({pr[rank1]:.5f})")

    # ---------- 8d. Menampilkan graph ----------
    st.subheader("Graph Hubungan Antar Website")

    components.html(
        graph_interaktif(G, pr, depth_pages),
        height=TINGGI_KOTAK
    )

    # ---------- 8e. Legenda warna ----------
    st.markdown("### Warna")

    st.markdown("""
    - 🟩 **Hijau terang (★, border tebal)** : PageRank peringkat 1
    - 🟥 **Merah** : Depth 0 (halaman awal)
    - 🟨 **Kuning** : Depth 1
    - 🟦 **Biru** : Depth 2
    - 🟪 **Ungu** : Depth 3
    - ⬜ **Abu-abu** : Kedalaman tidak teridentifikasi
    """)

    st.caption(
        "Klik node pada graph untuk melihat URL, kedalaman, "
        "dan nilai PageRank. Hover juga dapat menampilkan informasi."
    )

    # ---------- 8f. Tabel 10 PageRank tertinggi ----------
    top10_df = (
        pd.DataFrame(pr.items(), columns=["URL", "PageRank"])
        .sort_values("PageRank", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    top10_df.index += 1

    st.subheader("10 Website dengan PageRank Tertinggi")
    st.dataframe(top10_df, use_container_width=True)
