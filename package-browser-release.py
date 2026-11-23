#!/usr/bin/env python3
"""Create a browser source and relink package from the audited private build."""

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import zipfile

APP = Path(__file__).resolve().parent
WRAPPER_FILES = {
    "LICENSE",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.declarations.json",
    "vite.config.mts",
    "Docker/hicum2_patch.sh",
    "Docker/pre.js",
    "src/main.ts",
    "src/readOutput.ts",
    "src/simulationLink.ts",
    "src/spice.d.ts",
    "src/spice.js",
    "src/spice.wasm",
    "dist/eecircuit-engine.mjs",
}

NOTICE = (
    "Circuit Lab uses ngspice, including the LGPL-licensed Numparam and "
    "SuiteSparse components listed below. The source and relinking package "
    "contains the modified sources and linkable objects for the browser solver. "
    "See app/README.md and app/verify-portable.sh in that package for the "
    "build and relinking instructions.\n"
)


def audit_browser(package, engine, notices, worker=None):
    checks = runpy.run_path(str(APP / "audit-package.py"))
    ng, ee = checks["NG"], checks["EE"]
    digest = checks["SHA"]
    wrapper_root = f"work/{ee}/"
    expected_wrapper = {wrapper_root + name for name in WRAPPER_FILES}

    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 20000:
            raise ValueError("Unexpected browser source package inventory.")
        metadata = json.loads(archive.read("package.json"))
        if metadata.get("format") != "codi-ngspice-browser/1" or metadata.get("modelLicenses") != "excluded":
            raise ValueError("Unexpected browser source provenance.")
        if "work/engine.tar.gz" in names or {name for name in names if name.startswith(wrapper_root)} != expected_wrapper:
            raise ValueError("Unexpected redistribution inputs in the browser package.")
        if digest(archive.read("work/ngspice.tar.gz")) != checks["ARCHIVES"]["ngspice.tar.gz"]:
            raise ValueError("The ngspice source pin differs from the audited build.")
        wasm = archive.read(f"work/{ng}/release/src/spice.wasm")
        wrapper = archive.read(wrapper_root + "dist/eecircuit-engine.mjs")
        wasm_hash = metadata["wasmSha256"]
        if digest(wasm) != wasm_hash or digest(wrapper) != metadata["wrapperSha256"] or wrapper != engine.read_bytes():
            raise ValueError("The packaged binaries differ from the selected build.")
        checks["wasm_bindings"](wrapper, wasm_hash)
        if worker is not None:
            checks["wasm_bindings"](worker.read_bytes(), wasm_hash)
        notice_contents = [
            f"\n===== {name} =====\n" + archive.read(name).decode("utf-8", errors="replace")
            for name in sorted(names) if name.startswith("notices/")
        ]
        if notices.read_text(encoding="utf-8") != NOTICE + "".join(notice_contents):
            raise ValueError("The served notices differ from the source package.")
    return {
        "archiveSHA256": digest(package.read_bytes()), "wasmSHA256": wasm_hash,
        "wrapperSHA256": digest(wrapper), "noticeFiles": len(notice_contents),
        "workerChecked": worker is not None,
    }


def release(research, engine, research_notices, output):
    audit = runpy.run_path(str(APP / "audit-package.py"))
    receipt = audit["audit"](research, engine, research_notices)
    ng, ee = audit["NG"], audit["EE"]
    package = output / "source-relink.zip"
    notices = output / "NOTICES.txt"
    if package.exists() or notices.exists():
        raise FileExistsError("Choose a fresh release output directory.")
    output.mkdir(parents=True, exist_ok=True)
    wrapper_paths = {f"work/{ee}/{name}" for name in WRAPPER_FILES}

    with tempfile.TemporaryDirectory(prefix=".circuit-release-", dir=output) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(research) as archive, zipfile.ZipFile(
            staging / package.name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
        ) as result:
            source_names = set(archive.namelist())
            if not wrapper_paths <= source_names:
                raise ValueError("The pinned wrapper build inputs are incomplete.")
            metadata = json.loads(archive.read("package.json"))
            metadata["format"] = "codi-ngspice-browser/1"
            metadata["archives"] = {"ngspice.tar.gz": metadata["archives"]["ngspice.tar.gz"]}
            metadata["modelLicenses"] = "excluded"
            metadata.pop("warning", None)
            metadata["notice"] = "The wrapper source is restricted to the files used to build the browser solver."
            result.writestr("package.json", json.dumps(metadata, sort_keys=True, indent=2) + "\n")

            included_notices = []
            for name in sorted(source_names):
                if name.startswith("app/"):
                    relative = Path(name).relative_to("app")
                    if len(relative.parts) != 1 or not (APP / relative).is_file():
                        continue
                    result.writestr(archive.getinfo(name), (APP / relative).read_bytes())
                elif name.startswith("notices/"):
                    if name == "notices/FreePDK-APACHE-LICENSE-2.0.txt":
                        continue
                    contents = archive.read(name)
                    result.writestr(name, contents)
                    included_notices.append(f"\n===== {name} =====\n" + contents.decode("utf-8", errors="replace"))
                elif name == "work/ngspice.tar.gz" or name.startswith(f"work/{ng}/") or name in wrapper_paths:
                    result.writestr(archive.getinfo(name), archive.read(name))
            result.writestr("app/package-browser-release.py", Path(__file__).read_bytes())
            if {name for name in result.namelist() if name.startswith(f"work/{ee}/")} != wrapper_paths:
                raise ValueError("Unexpected wrapper files in the release package.")

        (staging / notices.name).write_text(NOTICE + "".join(included_notices), encoding="utf-8")
        audit_browser(staging / package.name, engine, staging / notices.name)
        (staging / package.name).rename(package)
        (staging / notices.name).rename(notices)
    with package.open("rb") as stream:
        print(json.dumps({
            "sourceArchiveSHA256": hashlib.file_digest(stream, "sha256").hexdigest(),
            "sourceArchiveBytes": package.stat().st_size,
            "wasmSHA256": receipt["wasmSHA256"],
            "wrapperSHA256": receipt["wrapperSHA256"],
            "wrapperSourceFiles": len(wrapper_paths),
            "noticeFiles": len(included_notices),
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("research", "engine", "research-notices", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    args = parser.parse_args()
    release(args.research, args.engine, args.research_notices, args.output)
