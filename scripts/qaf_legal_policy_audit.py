#!/usr/bin/env python3
"""QAF/SGAE: inventario reproducible de superficies legales y reglas conservadoras.

No interpreta silencio como consentimiento, no lee bases de datos, no modifica
cuentas ni activa permisos; no reemplaza asesoría legal.
Uso: python scripts/qaf_legal_policy_audit.py [--strict] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def audit(root: Path) -> dict:
    manifest_path = root / "config" / "qaf_legal" / "governance_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues: list[dict[str, str]] = []
    hashes: dict[str, str] = {}

    if manifest.get("publication_status") != "pending_legal_review":
        issues.append({"code": "unexpected_publication_status", "path": str(manifest_path.relative_to(root))})
    if manifest.get("commercial_opt_in_default") is not False:
        issues.append({"code": "commercial_consent_not_default_off", "path": str(manifest_path.relative_to(root))})
    for scope in manifest.get("commercial_scopes", []):
        if not isinstance(scope, str) or not re.fullmatch(r"[a-z_]+(?:\.[a-z_]+)*", scope):
            issues.append({"code": "invalid_scope", "path": str(manifest_path.relative_to(root))})

    for relative in manifest.get("source_documents", []):
        file = root / relative
        if not file.is_file():
            issues.append({"code": "missing_source_document", "path": relative})
            continue
        raw = file.read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        if "privacy" in relative.lower() or "privacidad" in relative.lower():
            if "privacy@gotogym.store" not in text:
                issues.append({"code": "privacy_contact_missing", "path": relative})

    if manifest.get("product") == "prime":
        policy = root / "gotogym" / "gotogym" / "politicas_contenido.py"
        if policy.is_file():
            source = policy.read_text(encoding="utf-8")
            refunds = source.split("DEVOLUCIONES =", 1)[-1].split("\nGARANTIA =", 1)[0]
            # La sección de devoluciones sigue siendo un borrador de corrección;
            # se marca el plazo anterior para revisión, nunca se cambia en silencio.
            if re.search(r"30\s+días\s+calendario", refunds):
                issues.append({"code": "retract_refund_period_needs_legal_review", "path": str(policy.relative_to(root))})
        else:
            issues.append({"code": "missing_refund_policy", "path": str(policy.relative_to(root))})

    return {
        "schema": "qaf.sgae.audit.v1",
        "product": manifest.get("product"),
        "status": manifest.get("publication_status"),
        "legal_review_required": True,
        "source_hashes_sha256": hashes,
        "issues": sorted(issues, key=lambda row: (row["code"], row["path"])),
        "ready_for_auto_publication": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Retorna error si existen hallazgos; usar después de revisión legal")
    parser.add_argument("--json", action="store_true", help="Imprime informe JSON")
    args = parser.parse_args()
    result = audit(repo_root())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"QAF SGAE {result['product']}: {len(result['issues'])} hallazgos; aprobación legal pendiente")
        for issue in result["issues"]:
            print(f"  {issue['code']}: {issue['path']}")
    return 1 if args.strict and result["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
