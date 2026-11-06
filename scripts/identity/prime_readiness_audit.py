#!/usr/bin/env python3
"""Read-only Prime OIDC production audit, safe to run in CI.

Does not obtain or print secret values, customer records or tokens.
Does not register Entra apps, modify App Service or migrate data.
"""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit

STATUS_URL = "https://shop.gotogym.store/accounts/identity/status/"
TENANT_ID = "fe3cd367-0570-48e7-8a35-a777b62cc6f9"
ISSUER = f"https://{TENANT_ID}.ciamlogin.com/{TENANT_ID}/v2.0"
DISCOVERY = (
    f"https://gotogymidentity.ciamlogin.com/{TENANT_ID}"
    "/v2.0/.well-known/openid-configuration"
)
CALLBACK = "https://shop.gotogym.store/accounts/oidc/callback/"
COACH_CLIENT_ID = "4fd1c894-78fa-496e-aaf2-5361da0dc430"
SUB = "c6015f72-55d5-4282-ba0b-f02152d798f7"
RG = "rg-gotogym-prime"
APP = "gotogym-prime"
VAULT_REFERENCE_SETTING = "OIDC_CLIENT_SECRET"
ARM = (
    f"https://management.azure.com/subscriptions/{SUB}/resourceGroups/{RG}"
    f"/providers/Microsoft.Web/sites/{APP}"
)
ALLOWED_BOOL = {"1", "true", "yes", "on"}


def _bool_setting(settings, name):
    value = settings.get(name)
    if value is None:
        return False
    return str(value).strip().lower() in ALLOWED_BOOL


def read_public_status(opener=None):
    """A public endpoint check; response is reduced to three booleans."""
    opener = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(
            STATUS_URL,
            headers={"Accept": "application/json", "User-Agent": "GoToGym-Prime-Identity-Audit/1"},
        )
        with opener(req, timeout=15) as response:
            if response.status != 200:
                return {"state": "unverified", "reason": "http_not_200"}
            obj = json.loads(response.read(4096))
        if (
            not isinstance(obj, dict)
            or any(type(obj.get(k)) is not bool for k in ("enabled", "canary", "ready"))
        ):
            return {"state": "unverified", "reason": "invalid_schema"}
        return {"state": "verified", **{k: obj[k] for k in ("enabled", "canary", "ready")}}
    except (OSError, TimeoutError, ValueError, urllib.error.URLError):
        return {"state": "unverified", "reason": "network_or_parse_error"}


def _az(*args):
    """Azure stdout is sensitive; never include it or stderr in diagnostics."""
    try:
        cmd = subprocess.run(
            ["az", *args, "--output", "json"], capture_output=True, text=True, timeout=75,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "azure_unavailable"
    if cmd.returncode:
        if "AuthorizationFailed" in cmd.stderr or "Forbidden" in cmd.stderr:
            return None, "azure_rbac_denied"
        if "ResourceNotFound" in cmd.stderr or "ResourceGroupNotFound" in cmd.stderr:
            return None, "azure_resource_unavailable"
        return None, "azure_request_failed"
    try:
        return json.loads(cmd.stdout), None
    except ValueError:
        return None, "azure_invalid_response"


def inspect_settings(settings):
    """Only boolean validations: never emit appsetting strings themselves."""
    if not isinstance(settings, list):
        return {"state": "unverified", "reason": "appsettings_unavailable"}
    values = {
        x["name"]: str(x.get("value") or "") for x in settings
        if isinstance(x, dict) and isinstance(x.get("name"), str)
    }
    client_id = values.get("OIDC_CLIENT_ID", "")
    secret = values.get(VAULT_REFERENCE_SETTING, "")
    parsed = urlsplit(values.get("OIDC_REDIRECT_URI", ""))
    callback_ok = (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "shop.gotogym.store"
        and parsed.path == "/accounts/oidc/callback/"
        and not parsed.query and not parsed.fragment
    )
    return {
        "state": "verified",
        "checks": {
            "issuer_exact": values.get("OIDC_ISSUER") == ISSUER,
            "discovery_exact": values.get("OIDC_DISCOVERY_URL") == DISCOVERY,
            "prime_client_id_present": bool(client_id),
            "prime_client_is_not_coach_client": bool(client_id) and client_id != COACH_CLIENT_ID,
            "secret_keyvault_reference_present": secret.startswith("@Microsoft.KeyVault("),
            "callback_exact": callback_ok,
            "post_logout_return": (
                values.get("OIDC_POST_LOGOUT_REDIRECT_URI") == "https://shop.gotogym.store/"
            ),
            "subject_claim_oid": values.get("OIDC_SUBJECT_CLAIM", "oid") == "oid",
            "legacy_login_available": not _bool_setting(values, "OIDC_SOLO_GOTOGYM"),
            "auto_create_disabled_initially": not _bool_setting(values, "OIDC_ALLOW_AUTO_CREATE"),
            "email_verified_claim_required": _bool_setting(
                values, "OIDC_REQUIRE_EMAIL_VERIFIED_CLAIM"
            ) or "OIDC_REQUIRE_EMAIL_VERIFIED_CLAIM" not in values,
        },
        "rollout": {
            "global": _bool_setting(values, "UNIVERSAL_IDENTITY_ENABLED"),
            "canary": _bool_setting(values, "UNIVERSAL_IDENTITY_CANARY_ENABLED"),
        },
    }


def _status_of_reference(obj):
    """Azure uses either list[value] or dictionary[properties] shapes."""
    records = []
    if isinstance(obj, dict):
        if isinstance(obj.get("value"), list):
            records = obj["value"]
        elif isinstance(obj.get("properties"), dict):
            records = [
                {"name": key, "properties": value}
                for key, value in obj["properties"].items()
            ]
    names = [
        x.get("properties", {}).get("status", "")
        for x in records
        if isinstance(x, dict)
        and x.get("name", "").split("/")[-1] == VAULT_REFERENCE_SETTING
        and isinstance(x.get("properties"), dict)
    ]
    if not names:
        return "unverified"
    return "resolved" if all(str(n).lower() == "resolved" for n in names) else "unresolved"


def read_azure():
    account, error = _az("account", "show")
    if error or not isinstance(account, dict):
        return {"state": "unverified", "reason": error or "account_unavailable"}
    if account.get("id") != SUB:
        return {"state": "unverified", "reason": "unexpected_subscription"}
    site, error = _az("webapp", "show", "--resource-group", RG, "--name", APP)
    if error or not isinstance(site, dict):
        return {"state": "unverified", "reason": error or "site_unavailable"}
    appsettings, error = _az(
        "webapp", "config", "appsettings", "list", "--resource-group", RG, "--name", APP
    )
    if error:
        return {"state": "unverified", "reason": error}
    settings = inspect_settings(appsettings)
    refs, ref_error = _az(
        "rest", "--method", "get",
        "--url", ARM + "/config/configreferences/appsettings?api-version=2023-12-01",
    )
    settings["keyvault_reference_status"] = (
        "unverified" if ref_error else _status_of_reference(refs)
    )
    settings["app_running"] = site.get("state") == "Running"
    settings["managed_identity_present"] = bool((site.get("identity") or {}).get("principalId"))
    return settings


def main():
    parser = argparse.ArgumentParser(description="Auditoria de solo lectura de OIDC Prime")
    parser.add_argument("--azure", action="store_true", help="Consultar App Service solo lectura")
    parser.add_argument("--strict", action="store_true", help="Fallará si Prime no está listo")
    args = parser.parse_args()
    output = {
        "mode": "read_only",
        "changes_performed": False,
        "end_to_end_microsoft_login": "not_tested",
        "public": read_public_status(),
    }
    if args.azure:
        output["azure"] = read_azure()
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.strict:
        public = output["public"]
        if public.get("state") != "verified" or not public.get("ready"):
            return 1
        if args.azure:
            azure = output["azure"]
            if (
                azure.get("state") != "verified"
                or not azure.get("app_running")
                or azure.get("keyvault_reference_status") != "resolved"
                or not all(azure.get("checks", {}).values())
            ):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
