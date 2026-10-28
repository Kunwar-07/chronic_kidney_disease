"""Download official, public NHANES components without overwriting originals."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parents[1]
COMPONENTS = ["DEMO", "BIOPRO", "ALB_CR", "BMX", "BPXO", "DIQ", "SMQ"]
CYCLES = {"2021-2023": (2021, "L"), "2017-2018": (2017, "J")}

def acquire(cycle):
    year, suffix = CYCLES[cycle]
    directory = BASE / "data/raw/official" / cycle
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = {"cycle": cycle, "population": "US civilian noninstitutionalized population; component-specific eligibility", "terms": "https://www.cdc.gov/nchs/policy/data-user-agreement.html", "files": []}
    for component in COMPONENTS:
        name = f"{component}_{suffix}"
        url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}.xpt"
        path = directory / f"{name}.xpt"
        previous = next((f for f in old.get("files", []) if f["name"] == name), None)
        if not path.exists():
            print(f"Downloading {name}", flush=True)
            with urlopen(Request(url, headers={"User-Agent": "CKD-Academic-Research/2.0"}), timeout=90) as response:
                content = response.read()
            if not content.startswith(b"HEADER RECORD"):
                raise ValueError(f"Expected SAS transport file, received other content: {url}")
            path.write_bytes(content)
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if previous and digest != previous["sha256"]:
            raise ValueError(f"Checksum changed for cached {path}; investigate before reuse")
        manifest["files"].append({"name": name, "url": url, "documentation": url[:-4] + ".htm", "retrieved_at": previous["retrieved_at"] if previous else datetime.now(timezone.utc).isoformat(), "sha256": digest, "bytes": len(content)})
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", choices=CYCLES, default="2021-2023")
    args = parser.parse_args()
    acquire(args.cycle)
