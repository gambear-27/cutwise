import sys
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import router from cad_router
from cad_router import router


def test_file(file_path_str: str):
    file_path = Path(file_path_str).resolve()
    if not file_path.is_file():
        print(f"[ERROR] File not found: {file_path}")
        print("Please provide a valid path to a .dwg, .dxf, .stl, or .obj file.")
        return

    print("=" * 75)
    print(f"Testing CAD True-Shape Extraction with:")
    print(f"File: {file_path.name}")
    print(f"Path: {file_path}")
    print(f"Size: {file_path.stat().st_size:,} bytes")
    print("=" * 75)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    print("Sending file to CAD True-Shape extraction module...")
    with open(file_path, "rb") as f:
        ext = file_path.suffix.lower()
        if ext == ".dwg":
            content_type = "application/acad"
        elif ext == ".dxf":
            content_type = "application/dxf"
        elif ext == ".stl":
            content_type = "model/stl"
        else:
            content_type = "application/octet-stream"

        response = client.post(
            "/cad/extract",
            files={"file": (file_path.name, f, content_type)}
        )

    print(f"Response Status: {response.status_code}")

    if response.status_code == 200:
        cut_list = response.json()
        print(f"\nSuccessfully extracted {len(cut_list)} unique true-shape part groups:\n")

        header = f"{'Part ID':<35} | {'Thick':<7} | {'Width':<8} | {'Length':<8} | {'Pts':<5} | {'Qty':<5} | {'Rotate':<6}"
        print(header)
        print("-" * len(header))
        for item in cut_list:
            part_id = item.get("part_id", "")
            thickness = item.get("thickness", 0.0)
            bbox = item.get("bounding_box") or item.get("dimensions") or {}
            w = bbox.get("width", 0.0)
            l = bbox.get("length", 0.0)
            contour = item.get("contour", [])
            qty = item.get("quantity", 1)
            rot = item.get("allow_rotation", True)
            print(f"{part_id:<35} | {thickness:<7.2f} | {w:<8.2f} | {l:<8.2f} | {len(contour):<5} | {qty:<5} | {str(rot):<6}")

        print("\nFull JSON Cut-List Output:")
        print(json.dumps(cut_list, indent=2))
    else:
        print(f"\n[FAILED] Error {response.status_code}:")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)


if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "dxf_r14/chair.dxf"
    test_file(target_file)
