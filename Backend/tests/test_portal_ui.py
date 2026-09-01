import pytest


@pytest.mark.django_db
class TestPortalUiShell:
    def test_admin_dashboard_uses_command_shell(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/administration/")
        assert response.status_code == 200
        html = response.content.decode()
        assert 'data-shell="administration"' in html
        assert 'name="q"' in html
        assert "nav-group" in html
        assert "chart-track" in html or "Needs attention" in html
        assert "user-chip" in html
        assert "nav-logout" in html

    def test_employee_dashboard_uses_work_tiles(self, client, kyc_user):
        client.force_login(kyc_user)
        html = client.get("/employee/").content.decode()
        assert 'data-shell="employee"' in html
        assert "work-tile" in html
        assert "Open queue" in html

    def test_merchant_dashboard_uses_progress_rail(self, client, merchant_user):
        client.force_login(merchant_user)
        html = client.get("/merchant/").content.decode()
        assert 'data-shell="merchant"' in html
        assert "progress-rail" in html
        assert "Start onboarding" in html

    def test_shells_use_nav_icons_and_ubuntu_css(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/").content.decode()
        assert "brand-wordmark" in html
        assert "images/logo/favicon-icon.png" in html
        assert "images/logo/logo-icon.png" in html
        assert "images/logo/logo-light.png" in html
        assert "nav-user" in html
        assert "user-name" in html
        assert "user-role" in html
        assert "Account settings" in html
        assert "Help &amp; support" not in html
        assert 'href="#i-home"' in html
        assert "empty-ico" in html
        from pathlib import Path

        css = Path("static/css/app.css").read_text()
        assert "font-family: Ubuntu" in css
        assert "ubuntu-400.woff2" in css
        assert "paper-sheet" in css
        assert "empty-ico" in css

    def test_login_uses_auth_illustration(self, client):
        html = client.get("/login/").content.decode()
        assert "auth-shell" in html
        assert "Sign in" in html
        assert "Welcome back" in html
        assert "Power of Banking" in html
        assert "auth-illustration" in html
        assert "auth-highlights" in html
        assert "auth-card-brand" in html
        assert "images/logo/payswap.png" in html
        assert "auth-card-logo" in html
        assert "images/logo/logo-light.png" not in html
        assert "/legal/grievance/" not in html
        assert "PayswapHub" not in html
        assert "Role is read from the account" not in html
        assert html.count('aria-label="Legal"') == 1
        assert "auth-panel" in html
        assert "auth-page" in html
        html_fail = client.post("/login/", {"email": "nobody@payswap.test", "password": "wrong"}).content.decode()
        assert "notice-ico" in html_fail
        assert "toast-close" in html_fail
        assert "The email or password is incorrect." in html_fail

    def test_search_stays_inside_portal_shell(self, client, merchant_user):
        client.force_login(merchant_user)
        html = client.get("/merchant/search/").content.decode()
        assert 'data-shell="merchant"' in html
        assert 'aria-label="Merchant"' in html
        assert "Help &amp; support" not in html
        assert "nav-logout" in html

    def test_staff_account_profile_is_editable(self, client, admin_user, kyc_user):
        client.force_login(admin_user)
        page = client.get("/administration/account/profile/")
        assert page.status_code == 200
        html = page.content.decode()
        assert "Sign-in details" in html
        assert 'data-shell="administration"' in html
        saved = client.post(
            "/administration/account/profile/",
            {"name": "Platform Admin", "mobile": "9876543210"},
        )
        assert saved.status_code == 302
        admin_user.refresh_from_db()
        assert admin_user.name == "Platform Admin"
        client.force_login(kyc_user)
        assert client.get("/employee/profile/").status_code == 200

    def test_orders_table_uses_server_pagination_and_datepicker(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/orders/").content.decode()
        # Server-paginated lists no longer load DataTables for in-page paging.
        assert "js-datatable" not in html
        assert "data-datepicker" in html
        assert "dataTables.min.js" in html

    def test_notifications_stays_inside_portal_shell(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/notifications/").content.decode()
        assert 'data-shell="administration"' in html
        assert "empty-state" in html or "Notifications" in html

    def test_no_inline_styles_on_flagged_pages(self, client, admin_user):
        client.force_login(admin_user)
        for path in [
            "/administration/",
            "/administration/merchants/",
            "/administration/onboarding/",
            "/administration/orders/",
            "/administration/audit/",
            "/administration/security/",
        ]:
            html = client.get(path).content.decode()
            # Allow the chart custom-property width pattern; forbid margin/layout styles
            import re

            stripped = re.sub(r'style="--w:\s*[\d.]+%"', "", html)
            assert 'style="' not in stripped, f"inline style leaked on {path}"

    def test_buttons_carry_explicit_type(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/merchants/").content.decode()
        # Buttons rendered by DataTables etc. are fine; assert form submit buttons are typed
        assert 'type="submit"' in html

    def test_shells_offer_collapse_and_breadcrumb_blocks(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/").content.decode()
        assert "data-nav-collapse" in html
        assert 'aria-controls="portal-nav"' in html

    def test_order_create_wizard_uses_stepper(self, client, merchant_user):
        client.force_login(merchant_user)
        html = client.get("/merchant/orders/new/").content.decode()
        assert "stepper-item" in html
        assert 'aria-label="Order steps"' in html
        assert "Order steps" in html

    def test_order_detail_uses_stepper(self, client, merchant_user, admin_user):
        from decimal import Decimal

        from catalog.models import Brand, ServiceType, VoucherProduct
        from merchants.models import Merchant
        from merchants.services import MerchantOnboardingService
        from orders.services import PaymentOrderService
        from tests.support import complete_required_draft

        client.force_login(merchant_user)
        application = MerchantOnboardingService.start(merchant_user, entity_type="PRIVATE_LIMITED")
        complete_required_draft(application)
        MerchantOnboardingService.submit(application, actor=merchant_user)
        MerchantOnboardingService.start_review(application, actor=admin_user)
        MerchantOnboardingService.approve(application, actor=admin_user)
        merchant = application.merchant
        merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
        merchant.agreement_status = Merchant.VerificationState.VERIFIED
        merchant.save(update_fields=["commercial_status", "agreement_status"])
        service, _ = ServiceType.objects.get_or_create(
            code="BRANDED_VOUCHER", defaults={"name": "Branded Voucher", "is_active": True}
        )
        brand, _ = Brand.objects.get_or_create(
            slug="amazon", defaults={"name": "Amazon", "service_type": service}
        )
        product, _ = VoucherProduct.objects.get_or_create(
            brand=brand,
            denomination=Decimal("1000.00"),
            defaults={"name": "Amazon ₹1,000", "fee_rate": Decimal("0.02"), "tax_rate": Decimal("0.18")},
        )
        order = PaymentOrderService.create(
            merchant=merchant, actor=merchant_user, product=product, quantity=10
        )
        PaymentOrderService.submit(order, actor=merchant_user)
        html = client.get(f"/merchant/orders/{order.public_id}/").content.decode()
        assert "stepper-item" in html

    def test_portal_shells_render_a_single_legal_footer(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get("/administration/").content.decode()
        assert html.count('aria-label="Legal"') == 1
        assert "site-footer" in html
