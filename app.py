from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
import networkx as nx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from pyvis.network import Network

MAX_PAGES = 50
SKIP = (".jpg", ".png", ".gif", ".pdf", ".zip", ".docx")


# ================= CRAWLING =================
def crawl(seed, max_depth):
    """Crawling BFS dan menyimpan kedalaman setiap halaman."""

    queue = deque([(seed, 0)])
    visited = {seed}
    edges = []
    depth_pages = {seed: 0}
    dibuka = 0

    while queue and dibuka < MAX_PAGES:
        url, depth = queue.popleft()

        try:
            html = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"}
            ).text
        except Exception:
            continue

        dibuka += 1

        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            link = urldefrag(urljoin(url, a["href"]))[0].rstrip("/")

            if (
                not link.startswith("http")
                or link == url
                or link.lower().endswith(SKIP)
            ):
                continue

            # Hanya menyimpan hubungan sampai kedalaman yang dipilih
            if depth < max_depth:
                edges.append((url, link))

                # Memasukkan halaman jika belum pernah ditemukan
                if link not in visited:
                    visited.add(link)
                    depth_pages[link] = depth + 1
                    queue.append((link, depth + 1))

    return edges, dibuka, depth_pages


# ================= GRAPH INTERAKTIF =================
def graph_interaktif(G, pr, depth_pages):
    """Graph berwarna berdasarkan depth dan menampilkan detail saat diklik."""

    urut = sorted(pr, key=pr.get, reverse=True)
    top10 = urut[:10]
    sub = G.subgraph(urut[:50])

    # Warna untuk setiap kedalaman
    warna_depth = {
        0: "#e4572e",  # Merah
        1: "#f4b942",  # Kuning
        2: "#76b5c5",  # Biru
        3: "#9b8bd5"   # Ungu
    }

    net = Network(
        height="650px",
        width="100%",
        directed=True,
        cdn_resources="in_line"
    )

    for n in sub.nodes():
        p = urlparse(n)
        d = depth_pages.get(n, -1)

        # Warna berdasarkan kedalaman
        warna = warna_depth.get(d, "#808080")

        net.add_node(
            n,
            label=p.netloc + p.path[:15] if n in top10 else " ",
            title=f"""
            URL: {n}<br>
            Kedalaman: {d}<br>
            PageRank: {pr[n]:.5f}
            """,
            size=10 + pr[n] * 600,
            color=warna
        )

    for a, b in sub.edges():
        net.add_edge(a, b)

    net.set_options("""{
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -6000,
          "springLength": 150,
          "damping": 0.6,
          "avoidOverlap": 0.5
        },
        "stabilization": {"iterations": 200}
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


# ================= TAMPILAN =================
st.title("Web Crawler & PageRank")

seed = st.text_input(
    "Link awal",
    "https://www.trunojoyo.ac.id"
)

depth = st.number_input(
    "Kedalaman",
    1,
    3,
    2
)


if st.button("Mulai Crawling"):

    with st.spinner("Sedang crawling..."):
        edges, dibuka, depth_pages = crawl(seed.rstrip("/"), depth)

    if not edges:
        st.error("Tidak ada link ditemukan. Coba link lain.")
        st.stop()

    # Membentuk graph
    G = nx.DiGraph(edges)

    # Menambahkan atribut kedalaman pada node
    nx.set_node_attributes(G, depth_pages, "depth")

    # Menghitung PageRank
    pr = nx.pagerank(G, alpha=0.85)

    # ================= METRIK =================
    m1, m2, m3 = st.columns(3)

    m1.metric("Halaman dibuka", dibuka)
    m2.metric("Jumlah node (halaman)", G.number_of_nodes())
    m3.metric("Jumlah edge (hubungan)", G.number_of_edges())

    # ================= GRAPH =================
    st.subheader("Graph Hubungan Antar Website")

    components.html(
        graph_interaktif(G, pr, depth_pages),
        height=670
    )

    # ================= LEGENDA =================
    st.markdown("### Keterangan Warna Kedalaman")

    st.markdown("""
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

    # ================= TOP 10 =================
    top10 = (
        pd.DataFrame(pr.items(), columns=["URL", "PageRank"])
        .sort_values("PageRank", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    top10.index += 1

    st.subheader("10 Website dengan PageRank Tertinggi")
    st.dataframe(top10)
