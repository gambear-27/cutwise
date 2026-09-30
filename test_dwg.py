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

    print("=" * 60)
    print(f"Testing CAD Geometry Extraction with:")
    print(f"File: {file_path.name}")
    print(f"Path: {file_path}")
    print(f"Size: {file_path.stat().st_size:,} bytes")
    print("=" * 60)

    # Spin up test client without needing a separate server process
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    print("Sending file to CAD extraction module...")
    with open(file_path, "rb") as f:
        # Determine content type
        ext = file_path.suffix.lower()
        content_type = "application/acad" if ext == ".dwg" else "application/dxf"
        
        response = client.post(
            "/cad/extract",
            files={"file": (file_path.name, f, content_type)}
        )

    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        cut_list = response.json()
        print(f"\nSuccessfully extracted {len(cut_list)} unique part dimension groups:\n")
        
        # Print tabular cut-list
        header = f"{'Part ID':<35} | {'Width':<10} | {'Length':<10} | {'Qty':<5} | {'Rotate':<6}"
        print(header)
        print("-" * len(header))
        for item in cut_list:
            part_id = item.get("part_id", "")
            dims = item.get("dimensions", {})
            w = dims.get("width", 0.0)
            l = dims.get("length", 0.0)
            qty = item.get("quantity", 1)
            rot = item.get("allow_rotation", True)
            print(f"{part_id:<35} | {w:<10} | {l:<10} | {qty:<5} | {str(rot):<6}")
        
        print("\nFull JSON Cut-List Output:")
        print(json.dumps(cut_list, indent=2))
    else:
        print(f"\n[FAILED] Error {response.status_code}:")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)

if __name__ == "__main__":
    # If user provided a path argument: python test_dwg.py "path/to/file.dwg"
    # Otherwise default to swivel_chair.dwg in current directory
    target_file = sys.argv[1] if len(sys.argv) > 1 else "swivel_chair.dwg"
    test_file(target_file)
