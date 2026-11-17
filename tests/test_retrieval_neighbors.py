"""第5回 宿題（実装）: 前後ページの追加はAPIを使わずに確かめる。"""

from app.retrieval import expand_neighbors, load_pages


def _hit(page, distance=0.1):
    return {**page, "distance": distance}


def test_radius_zero_returns_hits_unchanged():
    pages = load_pages()
    hits = [_hit(pages[10]), _hit(pages[3])]
    assert expand_neighbors(hits, radius=0) == hits


def test_neighbors_follow_each_hit_in_rank_order():
    pages = load_pages()
    hits = [_hit(pages[10]), _hit(pages[50])]
    results = expand_neighbors(hits, radius=1)
    ids = [r["page_id"] for r in results]
    assert ids == [pages[9]["page_id"], pages[10]["page_id"], pages[11]["page_id"],
                   pages[49]["page_id"], pages[50]["page_id"], pages[51]["page_id"]]
    assert [r["role"] for r in results] == ["prev", "hit", "next", "prev", "hit", "next"]
    assert results[0]["from"] == pages[10]["page_id"] and results[0]["distance"] is None
    assert results[1]["distance"] == 0.1


def test_duplicates_and_document_boundaries():
    pages = load_pages()
    first = next(p for p in pages if p["document_id"] == "lec02-main")   # 第2回の先頭ページ
    i = pages.index(first)
    results = expand_neighbors([_hit(first), _hit(pages[i + 1])], radius=1)
    ids = [r["page_id"] for r in results]
    assert len(ids) == len(set(ids))                      # 同じページは1回だけ
    assert all(r["document_id"] == "lec02-main" for r in results)   # 第1回の末尾へはまたがない
    assert ids[0] == first["page_id"] and results[0]["role"] == "hit"
    assert results[1]["role"] == "hit"                   # 2件目の当たりは prev/next ではなく hit のまま
