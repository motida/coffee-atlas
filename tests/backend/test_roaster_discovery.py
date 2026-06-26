"""Tests for the roaster-discovery stage.

Discovery turns specialty shops in ``shop_shops`` into a *review queue* of new
roaster storefronts. It must: only surface hosts not already covered (frontier
or existing roaster website), collapse shops sharing a host, write a staging
file in roaster_sites.txt format, and never touch the database. The network
probe is covered by the product_scraper's own fetch/extract tests; here we
exercise the pure selection + rendering logic and the DB read.
"""

from pathlib import Path

from backend.ingest.roaster_discovery import (
    Candidate,
    CandidateStub,
    _site_root,
    gather_stubs,
    known_hosts,
    render_candidates_file,
    select_candidates,
)


def test_site_root_normalizes_scheme_www_port_and_path():
    assert _site_root("https://www.Verve.com/pages/about") == "https://verve.com"
    assert _site_root("verve.com") == "https://verve.com"
    assert _site_root("http://verve.com:8080") == "https://verve.com"


def test_site_root_rejects_junk():
    assert _site_root("") is None
    assert _site_root("   ") is None
    assert _site_root(None) is None
    assert _site_root("not-a-host") is None  # no dot


def test_known_hosts_unions_frontier_and_roaster_websites(tmp_path):
    frontier = tmp_path / "sites.txt"
    frontier.write_text("# comment\nhttps://www.frontier.com\n\n", encoding="utf-8")

    hosts = known_hosts(["https://seeded.coffee/shop"], sites_file=frontier)

    assert hosts == {"frontier.com", "seeded.coffee"}


def test_known_hosts_tolerates_missing_frontier_file(tmp_path):
    hosts = known_hosts(["https://seeded.coffee"], sites_file=tmp_path / "absent.txt")
    assert hosts == {"seeded.coffee"}


def test_select_candidates_skips_known_and_dedupes_by_host():
    rows = [
        ("New Roaster", "Austin", "United States", "https://newroaster.com"),
        ("Already Scraped", "London", "United Kingdom", "https://known.com"),
        ("New Roaster 2nd Location", "Dallas", "United States", "https://www.newroaster.com/x"),
        ("No Website", None, None, ""),
    ]
    stubs = select_candidates(rows, known={"known.com"})

    assert [s.site for s in stubs] == ["https://newroaster.com"]
    assert stubs[0].shop_name == "New Roaster"  # first wins on shared host


def test_render_candidates_file_is_roaster_sites_format():
    candidates = [
        Candidate("https://b.com", "B Roasters", "Oslo", "Norway", "shopify", 12),
        Candidate("https://a.com", "A Coffee", None, None, "woocommerce", 3),
    ]
    text = render_candidates_file(candidates)
    lines = text.splitlines()

    # Sorted by site; each entry is a # provenance comment then the bare URL.
    assert "https://a.com" in lines
    assert "https://b.com" in lines
    assert lines.index("https://a.com") < lines.index("https://b.com")
    assert any("A Coffee — location unknown — woocommerce (3 products)" in ln for ln in lines)
    assert any("B Roasters — Oslo, Norway — shopify (12 products)" in ln for ln in lines)
    # Bare URLs survive read_sites' comment/blank filter.
    from backend.ingest.shop_scrapers.product_scraper import read_sites

    p = Path("/tmp/claude-roaster-discovery-render.txt")
    p.write_text(text, encoding="utf-8")
    assert set(read_sites(p)) == {"https://a.com", "https://b.com"}


def _insert_shop(db, sid, name, website, *, specialty=False, roasts=False, city=None, country=None):
    db.execute(
        """
        INSERT INTO shop_shops (id, name, website, is_specialty, roasts_in_house, city, country)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [sid, name, website, specialty, roasts, city, country],
    )


def test_gather_stubs_selects_only_specialty_or_roasting_shops_with_new_website(db, tmp_path):
    # Eligible: specialty w/ site, and roasts_in_house w/ site.
    _insert_shop(db, "s1", "Specialty Co", "https://specialty.example", specialty=True, city="LA")
    _insert_shop(db, "s2", "Roasts Here", "https://roastshere.example", roasts=True)
    # Ineligible: neither flag; flagged but no website; host already a roaster.
    _insert_shop(db, "s3", "Plain Cafe", "https://plain.example")
    _insert_shop(db, "s4", "No Site", None, specialty=True)
    _insert_shop(db, "s5", "Dup Of Roaster", "https://seeded.example", specialty=True)
    db.execute(
        "INSERT INTO roast_roasters (id, name, website) VALUES (?, ?, ?)",
        ["r1", "Seeded", "https://seeded.example"],
    )

    # Pure DB read — no network. Absent frontier file → empty frontier.
    stubs = gather_stubs(conn=db, sites_file=tmp_path / "frontier.txt")

    sites = sorted(s.site for s in stubs)
    assert sites == ["https://roastshere.example", "https://specialty.example"]
    # provenance carried through for the review file
    la = next(s for s in stubs if s.site == "https://specialty.example")
    assert la.shop_name == "Specialty Co" and la.city == "LA"
    # read-only: the DB was not mutated
    assert db.execute("SELECT COUNT(*) FROM roast_roasters").fetchone()[0] == 1


def test_candidate_stub_carries_provenance():
    stub = CandidateStub("https://x.com", "x.com", "X Roasters", "Berlin", "Germany")
    assert stub.host == "x.com"
    assert stub.shop_name == "X Roasters"
