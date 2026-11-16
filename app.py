from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
import networkx as nx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from pyvis.network import Network

MAX_PAGES = 50                                          # batas halaman yang dibuka
SKIP = (".jpg", ".png", ".gif", ".pdf", ".zip", ".docx")  # file yang bukan halaman web


def crawl(seed, max_depth):
    """Crawling BFS. Hasilnya daftar hubungan (halaman_asal, halaman_tujuan)."""
    queue = deque([(seed, 0)])
    visited = {seed}
    edges = []
    dibuka = 0

    while queue and dibuka < MAX_PAGES:
        url, depth = queue.popleft()
        try:
            html = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}).text
        except Exception:
            continue
        dibuka += 1

        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            link = urldefrag(urljoin(url, a["href"]))[0].rstrip("/")   # link absolut tanpa #
            if not link.startswith("http") or link == url or link.lower().endswith(SKIP):
                continue
            edges.append((url, link))                    # hubungan url -> link
            if depth < max_depth and link not in visited:
                visited.add(link)
                queue.append((link, depth + 1))          # di-crawl di level berikutnya
    return edges, dibuka


def graph_interaktif(G, pr):
    """Graph yang bisa digeser dan di-zoom. Merah = 10 PageRank tertinggi."""
    urut = sorted(pr, key=pr.get, reverse=True)
    top10 = urut[:10]
    sub = G.subgraph(urut[:50])                          # gambar 50 node teratas saja

    net = Network(height="650px", width="100%", directed=True, cdn_resources="in_line")
    for n in sub.nodes():
        p = urlparse(n)
        net.add_node(n,
                     label=p.netloc + p.path[:15] if n in top10 else " ",
                     title=f"{n}<br>PageRank: {pr[n]:.5f}",
                     size=10 + pr[n] * 600,
                     color="#e4572e" if n in top10 else "#76b5c5")
    for a, b in sub.edges():
        net.add_edge(a, b)

    net.set_options("""{
      "physics": {
        "barnesHut": {"gravitationalConstant": -6000, "springLength": 150, "damping": 0.6, "avoidOverlap": 0.5},
        "stabilization": {"iterations": 200}
      },
      "interaction": {"hover": true, "dragNodes": true, "zoomView": true},
      "edges": {"smooth": false}
    }""")

    html = net.generate_html()
    # setelah posisi node stabil, matikan fisika supaya graph diam dan tidak bergerak liar
    html = html.replace("return network;",
                        'network.once("stabilizationIterationsDone", function () { network.setOptions({physics: false}); });\n return network;')
    return html


# ================= Tampilan =================
st.title("Web Crawler & PageRank")
seed = st.text_input("Link awal", "https://www.trunojoyo.ac.id")
depth = st.number_input("Kedalaman", 1, 3, 2)

if st.button("Mulai Crawling"):
    with st.spinner("Sedang crawling..."):
        edges, dibuka = crawl(seed.rstrip("/"), depth)

    if not edges:
        st.error("Tidak ada link ditemukan. Coba link lain.")
        st.stop()

    G = nx.DiGraph(edges)                                # 1. bentuk graph dari hubungan
    pr = nx.pagerank(G, alpha=0.85)                      # 2. hitung PageRank

    m1, m2, m3 = st.columns(3)
    m1.metric("Halaman dibuka", dibuka)
    m2.metric("Jumlah node (halaman)", G.number_of_nodes())
    m3.metric("Jumlah edge (hubungan)", G.number_of_edges())

    st.subheader("Graph Hubungan Antar Website")
    components.html(graph_interaktif(G, pr), height=670)

    top10 = (pd.DataFrame(pr.items(), columns=["URL", "PageRank"])
               .sort_values("PageRank", ascending=False).head(10).reset_index(drop=True))
    top10.index += 1
    st.subheader("10 Website dengan PageRank Tertinggi")
    st.dataframe(top10)