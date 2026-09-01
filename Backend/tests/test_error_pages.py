import pytest


@pytest.mark.django_db
class TestErrorPages:
    def test_404_uses_branded_page(self, client, settings):
        settings.DEBUG = False
        response = client.get("/this-page-does-not-exist/")
        assert response.status_code == 404
        html = response.content.decode()
        assert "error-page" in html
        assert "Page not found" in html
        assert "payswap" in html
        assert "PayswapHub" not in html

    def test_403_uses_branded_page(self, client, merchant_user):
        client.force_login(merchant_user)
        response = client.get("/administration/")
        assert response.status_code == 403
        html = response.content.decode()
        assert "error-page" in html
        assert "Access denied" in html
        assert "/merchant/" in html

    def test_400_and_500_templates_render(self, rf, merchant_user):
        from portals.views.errors import bad_request, server_error

        request = rf.get("/broken/")
        request.user = merchant_user
        bad = bad_request(request, exception=Exception("bad"))
        boom = server_error(request)
        assert bad.status_code == 400
        assert b"Bad request" in bad.content
        assert boom.status_code == 500
        assert b"Something went wrong" in boom.content
        assert b"error-page" in boom.content

    def test_429_and_csrf_pages_render(self, rf):
        from portals.views.errors import csrf_failure, too_many_requests

        request = rf.post("/login/")
        request.user = type("Anon", (), {"is_authenticated": False})()
        limited = too_many_requests(request, exception=None)
        csrf = csrf_failure(request)
        assert limited.status_code == 429
        assert b"Too many attempts" in limited.content
        assert csrf.status_code == 403
        assert b"Session expired" in csrf.content
