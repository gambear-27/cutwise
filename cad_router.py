import os
import sys
import uuid
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional

# ==============================================================================
# Python Import Resolution
# Ensure current directory, parent directory, and project root are in sys.path
# so that schemas.py can be imported without ModuleNotFoundError regardless of how
# this file is executed (directly or as part of a package).
# ==============================================================================
_current_file = Path(__file__).resolve()
_search_dirs = [
    _current_file.parent,          # Directory containing cad_router.py
    _current_file.parent.parent,   # Parent directory (e.g. project root when inside a subfolder)
]

for _dir in _search_dirs:
    _dir_str = str(_dir)
    if _dir_str not in sys.path:
        sys.path.append(_dir_str)

import numpy as np
import trimesh
import ezdxf
import ezdxf.bbox
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from schemas import PartDimension, PartItem

# Router instance with prefix /cad
router = APIRouter(prefix="/cad", tags=["CAD Dimension Extraction"])

# ==============================================================================
# ODA File Converter Configuration
# Clear placeholder variable: update this with your local ODA File Converter path / version.
# Automatically detects installed version if present, or defaults to the standard path.
# ==============================================================================
_DEFAULT_ODA_PATH = (
    r"C:\Program Files\ODA\ODAFileConverter 27.9.0\ODAFileConverter.exe"
    if os.path.exists(r"C:\Program Files\ODA\ODAFileConverter 27.9.0\ODAFileConverter.exe")
    else r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
)

ODA_CONVERTER_PATH = os.getenv(
    "ODA_CONVERTER_PATH",
    os.getenv("ODA_FILE_CONVERTER_PATH", _DEFAULT_ODA_PATH)
)


def convert_dwg_to_dxf(dwg_path: Path, output_dir: Path) -> Path:
    """
    Converts a DWG file to DXF format by calling the ODA File Converter CLI.
    Robustly handles file paths with spaces, captures process errors, and runs headless.

    Args:
        dwg_path: Path to the input .dwg file.
        output_dir: Directory where the converted .dxf file will be saved.

    Returns:
        Path to the converted .dxf file.
    """
    converter_path = Path(ODA_CONVERTER_PATH)
    if not converter_path.is_file():
        raise FileNotFoundError(
            f"ODA File Converter executable not found at '{ODA_CONVERTER_PATH}'. "
            "Please ensure ODA File Converter is installed and update ODA_CONVERTER_PATH "
            "with your local installation path."
        )

    dwg_path = Path(dwg_path).resolve()
    if not dwg_path.is_file():
        raise FileNotFoundError(f"Input DWG file not found at '{dwg_path}'.")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = dwg_path.parent.resolve()

    # ODA File Converter CLI syntax:
    # ODAFileConverter <Input Dir> <Output Dir> <Output Version> <Output Type> <Recurse> <Audit> [Filter]
    # Note: subprocess.run automatically quotes arguments containing spaces on Windows when passed as a list.
    cmd = [
        str(converter_path),
        str(input_dir),
        str(output_dir),
        "ACAD2018",      # DXF target version
        "DXF",           # Target format
        "0",             # Recurse: 0 = false
        "1",             # Audit: 1 = true
        dwg_path.name    # Input file filter
    ]

    # Suppress console / GUI window popup on Windows
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            creationflags=creation_flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ODA File Converter timed out after 60 seconds converting '{dwg_path.name}'."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to execute ODA File Converter: {str(exc)}"
        ) from exc

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or f"Process exited with code {result.returncode}"
        raise RuntimeError(
            f"ODA File Converter failed with exit code {result.returncode}: {error_msg}"
        )

    # Locate the expected DXF output file
    expected_dxf = output_dir / f"{dwg_path.stem}.dxf"
    if expected_dxf.is_file():
        return expected_dxf

    # Case-insensitive / glob fallback search in the output directory
    dxf_matches = [f for f in output_dir.iterdir() if f.is_file() and f.suffix.lower() == ".dxf"]
    for match in dxf_matches:
        if match.stem.lower() == dwg_path.stem.lower():
            return match

    if dxf_matches:
        return dxf_matches[0]

    raise FileNotFoundError(
        f"Expected converted DXF file '{expected_dxf.name}' not found in '{output_dir}'. "
        f"Converter stdout: {result.stdout.strip()!r}, stderr: {result.stderr.strip()!r}"
    )


def extract_3d_dimensions(file_path: Path, file_stem: str) -> List[PartItem]:
    """
    Extracts flat 2D bounding box dimensions from a 3D CAD file (STL, OBJ).
    Loads the file as a scene, splits geometries into disconnected bodies,
    computes oriented bounding box extents, assumes the smallest dimension is
    material thickness, and maps the two largest dimensions to 2D width and length.
    """
    try:
        loaded = trimesh.load(str(file_path), force="scene")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse 3D CAD file: {str(e)}"
        )

    parts: List[PartItem] = []
    body_counter = 0

    # Collect all Trimesh geometries from the scene or loaded object
    if isinstance(loaded, trimesh.Scene):
        try:
            # dump() flattens graph nodes and applies world transformations
            geometries = [g for g in loaded.dump(concatenate=False) if isinstance(g, trimesh.Trimesh)]
        except Exception:
            geometries = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
    elif isinstance(loaded, trimesh.Trimesh):
        geometries = [loaded]
    else:
        geometries = []

    for geom in geometries:
        # Split geometry into disconnected bodies
        try:
            bodies = geom.split(only_watertight=False)
            if not isinstance(bodies, list):
                bodies = [bodies]
        except Exception:
            bodies = [geom]

        for body in bodies:
            if body.is_empty or len(body.vertices) == 0:
                continue

            try:
                obb = body.bounding_box_oriented
                extents = np.asarray(obb.extents, dtype=float)
                if extents.shape[0] != 3:
                    continue

                # Sort the 3 resulting dimensions:
                # Smallest is material thickness; two largest map to width and length
                sorted_dims = np.sort(extents)
                thickness = float(sorted_dims[0])
                width = round(float(sorted_dims[1]), 4)
                length = round(float(sorted_dims[2]), 4)

                if width <= 0 or length <= 0:
                    continue

                body_counter += 1
                parts.append(
                    PartItem(
                        part_id=f"{file_stem}_body_{body_counter}_{uuid.uuid4().hex[:6]}",
                        name=f"{file_stem}_body_{body_counter}",
                        dimensions=PartDimension(width=width, length=length),
                        quantity=1,
                        allow_rotation=True,
                    )
                )
            except Exception:
                continue

    return parts


def extract_dxf_dimensions(
    dxf_path: Path,
    file_stem: str,
    skip_insert: bool = False
) -> List[PartItem]:
    """
    Extracts flat 2D bounding box dimensions from a DXF file using ezdxf.
    Strictly uses ezdxf.bbox.extents([entity]) wrapped in try/except to prevent
    crashes with 3D INSERT blocks and unsupported entities.
    Optionally skips INSERT entities if specified.
    Ignores entities with width or length equal to 0.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse DXF file: {str(e)}"
        )

    msp = doc.modelspace()
    parts: List[PartItem] = []

    for idx, entity in enumerate(msp):
        entity_type = entity.dxftype()

        # Optionally skip INSERT entities
        if skip_insert and entity_type == "INSERT":
            continue

        # STRICT REQUIREMENT: strictly MUST use ezdxf.bbox.extents([entity]) wrapped in try/except
        try:
            box = ezdxf.bbox.extents([entity])
            if box is None or not box.has_data:
                continue
            width = abs(float(box.extmax.x - box.extmin.x))
            length = abs(float(box.extmax.y - box.extmin.y))
        except Exception:
            # Skip any entity that fails bounding box calculation (e.g. 3D solid blocks)
            continue

        # Ignore any entity where width or length equals 0
        if width == 0 or length == 0:
            continue

        width_rounded = round(width, 4)
        length_rounded = round(length, 4)
        if width_rounded == 0 or length_rounded == 0:
            continue

        part_id = f"{file_stem}_{entity_type}_{idx}_{uuid.uuid4().hex[:6]}"
        part_name = f"{file_stem}_{entity_type}_{idx}"

        parts.append(
            PartItem(
                part_id=part_id,
                name=part_name,
                dimensions=PartDimension(width=width_rounded, length=length_rounded),
                quantity=1,
                allow_rotation=True,
            )
        )

    return parts


def group_parts_by_dimensions(parts: List[PartItem]) -> List[PartItem]:
    """
    Groups parts with identical width and length dimensions.
    Merges them into a single PartItem and increments the quantity
    to compress the JSON payload for downstream nesting algorithms.
    When allow_rotation is True, orientation is normalized (min_dim, max_dim)
    so identically sized parts rotated by 90 degrees merge accurately.
    """
    grouped: dict[tuple[float, float], PartItem] = {}

    for part in parts:
        w = round(part.dimensions.width, 4)
        l = round(part.dimensions.length, 4)

        if part.allow_rotation:
            key = (min(w, l), max(w, l))
        else:
            key = (w, l)

        if key in grouped:
            grouped[key].quantity += part.quantity
        else:
            grouped[key] = PartItem(
                part_id=part.part_id,
                name=part.name,
                dimensions=PartDimension(
                    width=key[0] if part.allow_rotation else w,
                    length=key[1] if part.allow_rotation else l,
                ),
                quantity=part.quantity,
                allow_rotation=part.allow_rotation,
            )

    return list(grouped.values())


@router.post(
    "/extract",
    response_model=List[PartItem],
    summary="Extract flat 2D bounding box dimensions from CAD file",
    description="Extracts 2D dimensions from .dwg, .dxf, .stl, or .obj files and groups identical parts."
)
@router.post(
    "",
    response_model=List[PartItem],
    include_in_schema=False
)
async def extract_cad_dimensions(
    file: UploadFile = File(...),
    skip_insert: bool = False
) -> List[PartItem]:
    """
    Upload a CAD file (.dwg, .dxf, .stl, .obj) to extract flat 2D bounding box dimensions.
    Returns a compressed JSON list of PartItem objects with merged quantities.
    """
    filename = file.filename or ""
    file_ext = Path(filename).suffix.lower()

    supported_extensions = {".dwg", ".dxf", ".stl", ".obj"}
    if file_ext not in supported_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Supported formats: {', '.join(sorted(supported_extensions))}"
        )

    file_stem = Path(filename).stem or "cad_file"

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_file_path = temp_dir / filename

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        temp_file_path.write_bytes(content)

        extracted_parts: List[PartItem] = []

        if file_ext in {".stl", ".obj"}:
            extracted_parts = extract_3d_dimensions(temp_file_path, file_stem)
        elif file_ext == ".dxf":
            extracted_parts = extract_dxf_dimensions(temp_file_path, file_stem, skip_insert=skip_insert)
        elif file_ext == ".dwg":
            conversion_dir = temp_dir / "converted_dxf"
            try:
                converted_dxf_path = convert_dwg_to_dxf(temp_file_path, conversion_dir)
                extracted_parts = extract_dxf_dimensions(converted_dxf_path, file_stem, skip_insert=skip_insert)
            except FileNotFoundError as fnf_err:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(fnf_err)
                )
            except RuntimeError as rt_err:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(rt_err)
                )

        # Optimize payload by grouping parts with identical dimensions before returning
        return group_parts_by_dimensions(extracted_parts)


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    # Ensure parent directory is in sys.path so schemas.py in the parent directory imports correctly
    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.append(str(parent_dir))

    # Temporary FastAPI instance for testing
    app = FastAPI(
        title="CAD Dimension Extraction Service",
        description="Local test server for CAD 2D bounding box extraction router.",
        version="1.0.0",
    )

    # Include the CAD router
    app.include_router(router)

    # Root health-check endpoint
    @app.get("/", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "cad-extractor",
            "docs_url": "/docs"
        }

    # Run via uvicorn on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
