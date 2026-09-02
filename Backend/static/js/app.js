(function () {
    "use strict";

    var doc = document;

    /* ------------------------------------------------------------------
     * Menus (user chip / dropdowns) + click-outside
     * ------------------------------------------------------------------ */
    doc.addEventListener("click", function (event) {
        var trigger = event.target.closest("[data-menu-target]");
        if (trigger) {
            event.preventDefault();
            var menu = doc.getElementById(trigger.getAttribute("data-menu-target"));
            if (menu) {
                var open = menu.hasAttribute("hidden");
                menu.toggleAttribute("hidden", !open);
                trigger.setAttribute("aria-expanded", String(open));
                if (open) {
                    var first = menu.querySelector("a, button");
                    if (first) first.focus();
                }
            }
            return;
        }

        var navToggle = event.target.closest("[data-nav-toggle]");
        if (navToggle) {
            var nav = doc.getElementById(navToggle.getAttribute("aria-controls"));
            if (nav) {
                var isOpen = !nav.classList.contains("is-open");
                nav.classList.toggle("is-open", isOpen);
                navToggle.setAttribute("aria-expanded", String(isOpen));
                toggleScrim(isOpen, nav);
            }
            return;
        }

        var collapseBtn = event.target.closest("[data-nav-collapse]");
        if (collapseBtn) {
            var shell = doc.querySelector("[data-shell]");
            if (shell) {
                var collapsed = shell.classList.toggle("nav-collapsed");
                collapseBtn.setAttribute("aria-pressed", String(collapsed));
                try {
                    localStorage.setItem("payswap.navCollapsed", collapsed ? "1" : "0");
                } catch (err) {
                    /* private mode: ignore */
                }
            }
            return;
        }

        if (!event.target.closest(".user-chip, .menu")) {
            doc.querySelectorAll(".menu:not([hidden])").forEach(function (menu) {
                menu.setAttribute("hidden", "");
                var trigger = doc.querySelector('[data-menu-target="' + menu.id + '"]');
                if (trigger) trigger.setAttribute("aria-expanded", "false");
            });
        }
    });

    doc.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            doc.querySelectorAll(".menu:not([hidden])").forEach(function (menu) {
                menu.setAttribute("hidden", "");
                var trigger = doc.querySelector('[data-menu-target="' + menu.id + '"]');
                if (trigger) trigger.setAttribute("aria-expanded", "false");
            });
            var nav = doc.getElementById("portal-nav");
            if (nav && nav.classList.contains("is-open")) {
                nav.classList.remove("is-open");
                var toggle = doc.querySelector("[data-nav-toggle]");
                if (toggle) toggle.setAttribute("aria-expanded", "false");
                toggleScrim(false, nav);
            }
        }
    });

    doc.addEventListener("click", function (event) {
        var navLink = event.target.closest("#portal-nav a");
        if (navLink && window.innerWidth <= 900) {
            var nav = doc.getElementById("portal-nav");
            nav.classList.remove("is-open");
            var toggle = doc.querySelector("[data-nav-toggle]");
            if (toggle) toggle.setAttribute("aria-expanded", "false");
            toggleScrim(false, nav);
        }
    });

    function toggleScrim(show, nav) {
        var scrim = doc.querySelector(".nav-scrim");
        if (!scrim) {
            scrim = doc.createElement("div");
            scrim.className = "nav-scrim";
            scrim.setAttribute("aria-hidden", "true");
            nav.parentNode.appendChild(scrim);
        }
        scrim.classList.toggle("is-open", show);
    }

    /* ------------------------------------------------------------------
     * Mobile tables: inject data-label from <th> so stacked rows read well
     * ------------------------------------------------------------------ */
    function enhanceTableLabels() {
        doc.querySelectorAll("table:not([data-labels-done])").forEach(function (table) {
            var head = table.tHead;
            if (!head || !head.rows.length) return;
            var labels = Array.prototype.map.call(head.rows[0].cells, function (th) {
                return (th.textContent || "").trim();
            });
            Array.prototype.forEach.call(table.tBodies, function (tbody) {
                Array.prototype.forEach.call(tbody.rows, function (row) {
                    Array.prototype.forEach.call(row.cells, function (td, index) {
                        td.setAttribute("data-label", labels[index] || "");
                    });
                });
            });
            table.setAttribute("data-labels-done", "1");
        });
    }

    /* ------------------------------------------------------------------
     * Toasts / banners: close + auto-dismiss
     * ------------------------------------------------------------------ */
    function dismissNotice(node) {
        if (!node || !node.parentNode) return;
        node.remove();
        var host = doc.querySelector(".toasts");
        if (host && !host.querySelector(".toast")) host.remove();
    }

    function enhanceToasts() {
        doc.querySelectorAll(".toast[data-toast], .toast").forEach(function (toast) {
            if (toast.getAttribute("data-toast-ready")) return;
            toast.setAttribute("data-toast-ready", "1");
            var close = toast.querySelector(".toast-close");
            if (close) {
                close.addEventListener("click", function () {
                    dismissNotice(toast);
                });
            }
            var timeout = parseInt(toast.getAttribute("data-toast-timeout") || "5000", 10);
            if (timeout > 0) {
                setTimeout(function () {
                    dismissNotice(toast);
                }, timeout);
            }
        });
        doc.querySelectorAll(".banner .toast-close").forEach(function (close) {
            if (close.getAttribute("data-close-ready")) return;
            close.setAttribute("data-close-ready", "1");
            close.addEventListener("click", function () {
                dismissNotice(close.closest(".banner"));
            });
        });
    }

    /* ------------------------------------------------------------------
     * Client-side validation
     * ------------------------------------------------------------------ */
    var validators = {
        required: function (value) {
            return value.trim() ? "" : "This field is required.";
        },
        email: function (value) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
                ? ""
                : "Enter a valid email.";
        },
        mobile: function (value) {
            return /^[6-9]\d{9}$/.test(value)
                ? ""
                : "Enter a valid mobile number.";
        },
        pincode: function (value) {
            return /^[1-9][0-9]{5}$/.test(value)
                ? ""
                : "Enter a valid PIN code.";
        },
        password: function (value) {
            if (value.length < 10) {
                return "Password is too short.";
            }
            if (value.length > 64) {
                return "Password is too long.";
            }
            if (
                !/[a-z]/.test(value) ||
                !/[A-Z]/.test(value) ||
                !/[0-9]/.test(value) ||
                !/[^A-Za-z0-9]/.test(value)
            ) {
                return "Password does not meet the requirements.";
            }
            return "";
        },
        "confirm-password": function (value, input) {
            var form = input.form;
            var password = form ? form.querySelector("[data-validate='password']") : null;
            if (password && value !== password.value) {
                return "The passwords do not match.";
            }
            return value ? "" : "This field is required.";
        },
        otp: function (value) {
            return /^\d{6}$/.test(String(value || "").trim())
                ? ""
                : "Enter a valid OTP.";
        },
        terms: function (_value, input) {
            return input.checked
                ? ""
                : "Accept the Terms and Conditions and Privacy Policy.";
        },
    };

    function validateInput(input) {
        var type = input.getAttribute("data-validate");
        if (!type || !validators[type]) return true;
        var message = validators[type](input.value || "", input);
        var field = input.closest(".field");
        var alertNode = field ? field.querySelector("[data-field-alert]") : null;
        if (field) {
            field.classList.toggle("is-invalid", Boolean(message));
            field.classList.toggle("is-valid", !message && (input.type === "checkbox" ? input.checked : Boolean(input.value)));
        }
        if (alertNode) alertNode.textContent = message;
        input.setAttribute("aria-invalid", message ? "true" : "false");
        return !message;
    }

    doc.addEventListener("input", function (event) {
        var input = event.target;
        if (input.matches && input.matches("[data-validate]")) validateInput(input);
        if (input.matches && input.matches("[data-validate='terms']")) validateInput(input);
    });
    doc.addEventListener("change", function (event) {
        var input = event.target;
        if (input.matches && input.matches("[data-validate='terms']")) validateInput(input);
    });

    doc.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form.matches || !form.matches("[data-validate-form]")) return;
        var submitter = event.submitter;
        if (submitter && submitter.hasAttribute("formnovalidate")) return;
        var ok = true;
        form.querySelectorAll("[data-validate]").forEach(function (input) {
            if (!validateInput(input)) ok = false;
        });
        var box = form.querySelector(".form-alerts");
        if (!ok) {
            event.preventDefault();
            if (box && !box.querySelector(".banner-error, .alert-error")) {
                var alert = doc.createElement("div");
                alert.className = "banner banner-error";
                alert.setAttribute("role", "alert");
                alert.innerHTML =
                    '<svg class="notice-ico" aria-hidden="true"><use href="#i-alert"></use></svg>' +
                    '<p class="notice-body">Some fields are invalid.</p>' +
                    '<button type="button" class="toast-close" aria-label="Dismiss">' +
                    '<svg class="toast-close-ico" aria-hidden="true"><use href="#i-close"></use></svg></button>';
                box.prepend(alert);
                box.style.display = "grid";
                enhanceToasts();
            }
        }
    });

    /* Page loader on real submits */
    doc.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return;
        var loader = doc.querySelector("[data-page-loader]");
        if (loader) {
            loader.hidden = false;
            loader.setAttribute("aria-busy", "true");
        }
    });

    /* ------------------------------------------------------------------
     * Password reveal
     * ------------------------------------------------------------------ */
    function enhancePasswordFields() {
        doc.querySelectorAll("input[type='password']").forEach(function (input) {
            if (input.closest("[data-password-wrap]")) return;
            var wrap = doc.createElement("div");
            wrap.className = "password-wrap";
            wrap.setAttribute("data-password-wrap", "");
            input.parentNode.insertBefore(wrap, input);
            wrap.appendChild(input);
            var button = doc.createElement("button");
            button.type = "button";
            button.className = "password-toggle";
            button.setAttribute("aria-label", "Show password");
            button.textContent = "Show";
            button.addEventListener("click", function () {
                var hidden = input.type === "password";
                input.type = hidden ? "text" : "password";
                button.textContent = hidden ? "Hide" : "Show";
                button.setAttribute("aria-label", hidden ? "Hide password" : "Show password");
            });
            wrap.appendChild(button);
        });
    }

    /* ------------------------------------------------------------------
     * Date pickers (flatpickr when present)
     * ------------------------------------------------------------------ */
    function enhanceDatePickers() {
        if (!window.flatpickr) return;
        doc.querySelectorAll("[data-datepicker]").forEach(function (input) {
            window.flatpickr(input, {
                dateFormat: "Y-m-d",
                allowInput: true,
                disableMobile: true,
            });
        });
    }

    /* ------------------------------------------------------------------
     * DataTables when present
     * ------------------------------------------------------------------ */
    function enhanceDataTables() {
        var tables = doc.querySelectorAll("table.js-datatable");
        if (!tables.length) return;
        tables.forEach(function (table) {
            if (table.tBodies[0] && table.tBodies[0].rows.length === 0) return;
            var exportButtons = table.getAttribute("data-table-export") === "true";
            var pageLength = parseInt(table.getAttribute("data-page-length") || "10", 10);
            var options = {
                responsive: true,
                autoWidth: false,
                pageLength: isNaN(pageLength) ? 10 : pageLength,
                order: [],
                layout: {
                    topStart: exportButtons ? { buttons: ["copy", "csv", "excel", "print"] } : "pageLength",
                    topEnd: "search",
                    bottomStart: "info",
                    bottomEnd: "paging",
                },
                language: {
                    search: "",
                    searchPlaceholder: "Filter this table",
                    lengthMenu: "Show _MENU_",
                    emptyTable: "Nothing to show yet.",
                    zeroRecords: "No matching rows.",
                },
            };
            if (window.jQuery && window.jQuery.fn && window.jQuery.fn.DataTable) {
                window.jQuery(table).DataTable(options);
                return;
            }
            if (window.DataTable) {
                new window.DataTable(table, options);
            }
        });
    }

    /* ------------------------------------------------------------------
     * PIN code autofill (India Post lookup)
     * ------------------------------------------------------------------ */
    function enhancePincodeFields() {
        doc.querySelectorAll("[data-pincode-lookup]").forEach(function (input) {
            var hint = input.closest(".field")
                ? input.closest(".field").querySelector("[data-pincode-hint]")
                : input.parentElement.querySelector("[data-pincode-hint]");
            var url = input.getAttribute("data-pincode-url");
            if (!hint || !url) return;
            input.addEventListener("change", function () {
                var pin = input.value.replace(/\D/g, "");
                if (pin.length !== 6) {
                    hint.textContent = "";
                    return;
                }
                hint.textContent = "Looking up PIN code…";
                fetch(url + "?pin=" + encodeURIComponent(pin), {
                    headers: { Accept: "application/json" },
                    credentials: "same-origin",
                })
                    .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
                    .then(function (result) {
                        if (result.ok) {
                            hint.textContent = result.body.area + ", " + result.body.district + ", " + result.body.state;
                        } else {
                            hint.textContent = result.body.error || "PIN code could not be verified.";
                        }
                    })
                    .catch(function () {
                        hint.textContent = "PIN code could not be verified.";
                    });
            });
        });
    }

    /* ------------------------------------------------------------------
     * Boot: restore collapsed nav preference
     * ------------------------------------------------------------------ */
    function restoreNavPreference() {
        var shell = doc.querySelector("[data-shell]");
        if (!shell) return;
        var collapsed = false;
        try {
            collapsed = localStorage.getItem("payswap.navCollapsed") === "1";
        } catch (err) {
            /* ignore */
        }
        if (collapsed && window.innerWidth > 900) {
            shell.classList.add("nav-collapsed");
        }
        var btn = doc.querySelector("[data-nav-collapse]");
        if (btn) btn.setAttribute("aria-pressed", String(collapsed));
    }

    doc.addEventListener("DOMContentLoaded", function () {
        restoreNavPreference();
        enhancePasswordFields();
        enhanceDatePickers();
        enhanceDataTables();
        enhanceToasts();
        enhanceTableLabels();
        enhancePincodeFields();
        enhanceEntityFields();
        enhanceOtpGroups();
        enhanceOtpCountdowns();
    });

    function enhanceOtpCountdowns() {
        doc.querySelectorAll("[data-otp-countdown]").forEach(function (el) {
            if (el.getAttribute("data-otp-ready")) return;
            el.setAttribute("data-otp-ready", "1");
            var remaining = parseInt(el.getAttribute("data-seconds") || "0", 10);
            var resend = el.parentElement && el.parentElement.querySelector("[data-otp-resend]");

            function format(sec) {
                var mins = Math.floor(sec / 60);
                var secs = sec % 60;
                return "Resend in " + mins + ":" + String(secs).padStart(2, "0");
            }

            function done() {
                el.hidden = true;
                if (resend) resend.hidden = false;
            }

            if (remaining <= 0) {
                done();
                return;
            }
            el.hidden = false;
            if (resend) resend.hidden = true;
            el.textContent = format(remaining);
            var timer = window.setInterval(function () {
                remaining -= 1;
                if (remaining <= 0) {
                    window.clearInterval(timer);
                    done();
                    return;
                }
                el.textContent = format(remaining);
            }, 1000);
        });
    }

    function enhanceOtpGroups() {
        doc.querySelectorAll("[data-otp-group]").forEach(function (group) {
            if (group.getAttribute("data-otp-ready")) return;
            group.setAttribute("data-otp-ready", "1");
            var hidden = group.querySelector("[data-otp-value]");
            var digits = Array.prototype.slice.call(group.querySelectorAll(".otp-digit"));
            if (!hidden || !digits.length) return;

            function sync() {
                hidden.value = digits.map(function (box) {
                    return String(box.value || "").replace(/\D/g, "").slice(0, 1);
                }).join("");
            }

            digits.forEach(function (input, index) {
                input.addEventListener("input", function () {
                    var raw = String(input.value || "").replace(/\D/g, "");
                    if (raw.length > 1) {
                        raw.slice(0, digits.length - index).split("").forEach(function (ch, offset) {
                            if (digits[index + offset]) digits[index + offset].value = ch;
                        });
                        var next = digits[Math.min(index + raw.length, digits.length - 1)];
                        if (next) next.focus();
                    } else {
                        input.value = raw;
                        if (raw && digits[index + 1]) digits[index + 1].focus();
                    }
                    sync();
                    if (hidden.hasAttribute("data-validate")) validateInput(hidden);
                });
                input.addEventListener("keydown", function (event) {
                    if (event.key === "Backspace" && !input.value && index > 0) {
                        event.preventDefault();
                        digits[index - 1].value = "";
                        digits[index - 1].focus();
                        sync();
                    }
                    if (event.key === "ArrowLeft" && index > 0) digits[index - 1].focus();
                    if (event.key === "ArrowRight" && digits[index + 1]) digits[index + 1].focus();
                });
                input.addEventListener("paste", function (event) {
                    var text = (event.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
                    if (!text) return;
                    event.preventDefault();
                    digits.forEach(function (box, offset) {
                        box.value = text[offset] || "";
                    });
                    sync();
                    var focusAt = digits[Math.min(text.length, digits.length) - 1];
                    if (focusAt) focusAt.focus();
                    if (hidden.hasAttribute("data-validate")) validateInput(hidden);
                });
            });
        });
    }

    function enhanceEntityFields() {
        doc.querySelectorAll("[data-entity-form]").forEach(function (form) {
            var select = form.querySelector("[data-entity-select]");
            if (!select) return;
            function sync() {
                var value = select.value;
                form.querySelectorAll("[data-entities]").forEach(function (el) {
                    var allowed = (el.getAttribute("data-entities") || "").split(/\s+/);
                    var show = allowed.indexOf(value) !== -1;
                    el.hidden = !show;
                    el.querySelectorAll("input, select, textarea").forEach(function (input) {
                        input.disabled = !show;
                    });
                });
            }
            select.addEventListener("change", sync);
            sync();
        });
    }

    doc.addEventListener("submit", function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        // A message on the clicked button wins over one on the form, so a form
        // carrying several actions can confirm only the destructive ones.
        var submitter = event.submitter;
        var message =
            (submitter && submitter.getAttribute("data-confirm-submit")) ||
            form.getAttribute("data-confirm-submit");
        if (!message) return;
        if (!window.confirm(message)) {
            event.preventDefault();
            event.stopPropagation();
        }
    }, true);
})();
