import base64
import zlib

from eil.publication import ROOT, identity_issues, scan_content


def test_publication_rejects_home_paths_and_credentials_without_echoing_values():
    path = b"C:" + b"/Users/" + b"person/private.txt"
    secret = b"ghp_" + b"A" * 36
    assert scan_content("example.txt", path) == ["personal workstation home path"]
    assert scan_content("example.txt", secret) == ["credential pattern"]
    assert not scan_content("api.py", b"/api/auth/users/{user_id}/update")


def test_publication_checks_emails_and_no_reply_commit_identities():
    private = b"person@" + b"private.test"
    assert scan_content("example.txt", private) == ["non-example email address"]
    assert not scan_content("example.txt", b"member@example.com")
    assert not identity_issues(b"public-handle", b"123+public-handle@users.noreply.github.com")
    assert identity_issues(b"public-handle", private)


def test_licensed_attribution_is_retained_but_does_not_exempt_secrets():
    public_contact = b"author@" + b"licensed-source.test"
    assert not scan_content("data/public-machine-packs/demo/LICENSE.txt", public_contact)
    assert scan_content("data/public-machine-packs/demo/source.md", b"ghp_" + b"B" * 36)


def test_publication_inspects_encoded_pdf_content_and_image_metadata():
    text = b"C:" + b"/Users/" + b"person/private.txt"
    encoded = base64.a85encode(zlib.compress(text), adobe=True)
    pdf = b"%PDF-1.3\n/Filter [ /ASCII85Decode /FlateDecode ]\nstream\n" + encoded + b"\nendstream"
    assert "personal workstation home path" in scan_content("synthetic.pdf", pdf)
    assert scan_content("photo.jpg", b"header Exif\x00\x00 metadata")
    assert not scan_content("synthetic.pdf", (ROOT / "output/pdf/m5-known-cause.pdf").read_bytes())
