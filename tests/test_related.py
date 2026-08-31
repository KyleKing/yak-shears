"""Ranking of related notes."""

from yak_shears._yak.related import rank_related

TITLES = {"me.dj": "Me", "near.dj": "Near", "far.dj": "Far", "cited.dj": "Cited"}


def test_shared_links_outrank_shared_tags_and_every_reason_is_named():
    edges = [
        ("me.dj", "shared-a", "wikilink"),
        ("me.dj", "shared-b", "wikilink"),
        ("me.dj", "python", "tag"),
        ("near.dj", "shared-a", "wikilink"),
        ("near.dj", "shared-b", "wikilink"),
        ("far.dj", "python", "tag"),
    ]
    ranked = rank_related("me.dj", edges, TITLES)

    assert [relation.path for relation in ranked] == ["near.dj", "far.dj"]
    assert ranked[0].reasons == ["2 shared links"]
    assert ranked[1].reasons == ["1 shared tag"]


def test_co_citation_counts_notes_cited_alongside_this_one():
    edges = [
        ("near.dj", "me", "wikilink"),
        ("near.dj", "cited", "wikilink"),
        ("far.dj", "me", "wikilink"),
        ("far.dj", "cited", "wikilink"),
    ]
    ranked = {relation.path: relation for relation in rank_related("me.dj", edges, TITLES)}

    assert ranked["cited.dj"].reasons == ["cited with it by 2 notes"]
    assert "me.dj" not in ranked


def test_a_note_with_nothing_in_common_is_left_off():
    edges = [("me.dj", "alone", "wikilink"), ("far.dj", "elsewhere", "wikilink")]
    assert rank_related("me.dj", edges, TITLES) == []
