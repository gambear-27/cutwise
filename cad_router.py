import os
import sys
import uuid
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

# ==============================================================================
# Python Import Resolution
# Ensure current directory and parent directory are in sys.path so schemas.py
# can be imported without ModuleNotFoundError regardless of execution context.
# ==============================================================================
_current_file = Path(__file__).resolve()
_search_dirs = [
    _current_file.parent,          # Directory containing cad_router.py
    _current_file.parent.parent,   # Parent directory
]

for _dir in _search_dirs:
    _dir_str = str(_dir)
    if _dir_str not in sys.path:
        sys.path.append(_dir_str)

import numpy as np
import trimesh
import ezdxf
import ezdxf.path
import ezdxf.bbox
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.ops import polygonize, unary_union
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from schemas import BoundingBox, PartDimension, PartItem

# Router instance with prefix /cad
router = APIRouter(prefix="/cad", tags=["CAD True-Shape Extraction"])

# ==============================================================================
# ODA File Converter Configuration
# Automatically detects installed ODA File Converter version or defaults to standard path.
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

    expected_dxf = output_dir / f"{dwg_path.stem}.dxf"
    if expected_dxf.is_file():
        return expected_dxf

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


def generate_svg_with_labels(
    contour: List[List[float]],
    holes: Optional[List[List[List[float]]]] = None,
    thickness: float = 0.0,
    radius: Optional[float] = None
) -> str:
    """
    Generates a clean vector SVG string representation of a 2D contour including:
    - Outer boundary path
    - Inner hole cutouts (using evenodd fill-rule)
    - Embedded text label displaying calculated Material Thickness and Curve Radius.
    """
    if not contour:
        return ""

    holes = holes or []
    xs = [pt[0] for pt in contour]
    ys = [pt[1] for pt in contour]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    w = max(1.0, max_x - min_x)
    h = max(1.0, max_y - min_y)
    pad = max(w, h) * 0.12

    view_min_x = min_x - pad
    view_min_y = min_y - pad
    view_w = w + 2 * pad
    view_h = h + 2 * pad

    # Outer path string
    path_d = f"M {contour[0][0]} {contour[0][1]} " + " ".join(f"L {pt[0]} {pt[1]}" for pt in contour[1:]) + " Z"

    # Inner holes paths
    for hole in holes:
        if len(hole) >= 3:
            path_d += f" M {hole[0][0]} {hole[0][1]} " + " ".join(f"L {pt[0]} {pt[1]}" for pt in hole[1:]) + " Z"

    label_parts = [f"T: {thickness:.2f}"]
    if radius is not None and radius > 0:
        label_parts.append(f"R: {radius:.2f}")
    label_text = " | ".join(label_parts)

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    font_size = max(1.0, max(w, h) * 0.05)
    stroke_w = max(0.5, max(w, h) / 80.0)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_min_x:.2f} {view_min_y:.2f} {view_w:.2f} {view_h:.2f}">'
        f'<path d="{path_d}" fill="rgba(59, 130, 246, 0.22)" stroke="#3b82f6" stroke-width="{stroke_w:.2f}" fill-rule="evenodd"/>'
        f'<text x="{center_x:.2f}" y="{center_y:.2f}" font-family="sans-serif" font-size="{font_size:.2f}" font-weight="bold" fill="#fbbf24" text-anchor="middle" dominant-baseline="middle">{label_text}</text>'
        f'</svg>'
    )
    return svg


def group_surface_normals(normals: np.ndarray, atol: float = 1e-2) -> List[Dict[str, Any]]:
    """
    Groups surface normal vectors across ALL angles with relaxed floating-point tolerance (atol=1e-2)
    so coplanar triangles with minor STL export rounding errors are correctly grouped together.
    """
    clusters: List[Dict[str, Any]] = []

    for i, n in enumerate(normals):
        norm = np.linalg.norm(n)
        if norm < 1e-6:
            continue
        n_unit = n / norm

        found = False
        for c in clusters:
            # Unorient vector check: coplanar parallel faces (+N and -N) share orientation plane
            if abs(np.dot(n_unit, c["normal"])) >= (1.0 - atol):
                c["indices"].append(i)
                found = True
                break

        if not found:
            clusters.append({"normal": n_unit, "indices": [i]})

    return clusters


def detect_curved_features(body: trimesh.Trimesh, atol: float = 1e-2) -> List[Dict[str, Any]]:
    """
    Recognizes and measures curved geometries (cylinders, fillets, circular holes, pins)
    approximated by flat triangular facets in STL files.
    Groups facets, fits 2D circles, calculates radii, center coordinates, and extrusion depth.
    """
    features: List[Dict[str, Any]] = []
    normals = body.face_normals
    if len(normals) < 6:
        return features

    # Check candidate curve axes (principal axes X, Y, Z or PCA axes)
    candidate_axes = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    ]

    for axis in candidate_axes:
        axis_unit = axis / np.linalg.norm(axis)
        dots = np.abs(np.dot(normals, axis_unit))

        # Curved facets are orthogonal to curve axis (dot product near 0)
        side_mask = dots < (10.0 * atol)
        if np.sum(side_mask) >= 6:
            side_faces = body.faces[side_mask]
            vertex_indices = np.unique(side_faces)

            # Align axis to Z
            rot_matrix = trimesh.geometry.align_vectors(axis_unit, np.array([0.0, 0.0, 1.0]))
            aligned = body.copy().apply_transform(rot_matrix)

            pts2d = aligned.vertices[vertex_indices][:, :2]
            z_coords = aligned.vertices[vertex_indices][:, 2]
            depth = float(z_coords.max() - z_coords.min())

            if len(pts2d) < 6 or depth <= 0:
                continue

            # Fit 2D circle using least squares: (x - xc)^2 + (y - yc)^2 = R^2
            x = pts2d[:, 0]
            y = pts2d[:, 1]
            A_mat = np.column_stack([x, y, np.ones_like(x)])
            b_vec = x**2 + y**2

            try:
                c_sol, res, rank, s = np.linalg.lstsq(A_mat, b_vec, rcond=None)
                xc = float(c_sol[0] / 2.0)
                yc = float(c_sol[1] / 2.0)
                r = float(np.sqrt(max(0, c_sol[2] + xc**2 + yc**2)))

                dists = np.sqrt((x - xc)**2 + (y - yc)**2)
                rel_err = float(np.std(dists) / r) if r > 0 else 1.0

                # If relative radial standard deviation < 5%, it's a verified true curve
                if rel_err < 0.05 and r > 1e-3:
                    features.append({
                        "axis": axis_unit,
                        "radius": round(r, 4),
                        "depth": round(depth, 4),
                        "center": (round(xc, 4), round(yc, 4)),
                        "rot_matrix": rot_matrix,
                    })
            except Exception:
                continue

    return features


def extract_3d_true_shapes(file_path: Path, file_stem: str) -> List[PartItem]:
    """
    Upgraded 3D Pipeline (STL, OBJ via trimesh):
    - Processes ALL unique surface normal angles across 3D geometry.
    - Relaxes floating-point tolerances (atol=1e-2).
    - Removes minimum area thresholds (preserves thin lips, micro-cutouts, small features).
    - Merges adjacent coplanar triangles into continuous 2D polygon outlines (outer boundaries + inner holes).
    - Recognizes and measures curved geometries (cylinders, holes, fillets), calculating radii and depth.
    - Outputs material thickness and embeds text labels in final SVG string output.
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

    if isinstance(loaded, trimesh.Scene):
        try:
            geometries = [g for g in loaded.dump(concatenate=False) if isinstance(g, trimesh.Trimesh)]
        except Exception:
            geometries = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
    elif isinstance(loaded, trimesh.Trimesh):
        geometries = [loaded]
    else:
        geometries = []

    for geom in geometries:
        try:
            bodies = geom.split(only_watertight=False)
            if not isinstance(bodies, list):
                bodies = [bodies]
        except Exception:
            bodies = [geom]

        for body in bodies:
            if body.is_empty or len(body.vertices) == 0:
                continue

            body_counter += 1

            # 1. Curve & Cylinder Recognition
            curved_feats = detect_curved_features(body)
            processed_curve_axes = set()

            for feat in curved_feats:
                r = feat["radius"]
                depth = feat["depth"]
                xc, yc = feat["center"]

                # Generate 2D circle contour representation
                angles = np.linspace(0, 2 * np.pi, 64, endpoint=True)
                contour = [[round(xc + r * np.cos(a), 4), round(yc + r * np.sin(a), 4)] for a in angles]
                if contour[0] != contour[-1]:
                    contour.append(contour[0])

                xs = [pt[0] for pt in contour]
                ys = [pt[1] for pt in contour]
                w = round(max(xs) - min(xs), 4)
                l = round(max(ys) - min(ys), 4)

                part_id = f"{file_stem}_curve_r{int(r*100)}_{uuid.uuid4().hex[:6]}"
                part_name = f"{file_stem}_curved_feature_r{r}"

                svg = generate_svg_with_labels(contour, holes=[], thickness=depth, radius=r)

                parts.append(
                    PartItem(
                        part_id=part_id,
                        name=part_name,
                        thickness=depth,
                        radius=r,
                        contour=contour,
                        holes=[],
                        bounding_box=BoundingBox(width=w, length=l),
                        svg_path=svg,
                        quantity=1,
                        allow_rotation=True,
                    )
                )

            # 2. Process ALL Unique Surface Normal Angles across 3D geometry
            normal_clusters = group_surface_normals(body.face_normals, atol=1e-2)

            for cluster_idx, cluster in enumerate(normal_clusters):
                primary_normal = cluster["normal"]
                face_indices = cluster["indices"]

                # Align body to Z-axis for this normal angle
                rot_matrix = trimesh.geometry.align_vectors(primary_normal, np.array([0.0, 0.0, 1.0]))
                aligned = body.copy().apply_transform(rot_matrix)

                # Material thickness along surface normal (perpendicular distance to opposite parallel face / depth)
                z_coords = aligned.vertices[:, 2]
                thickness = round(float(z_coords.max() - z_coords.min()), 4)

                v2d = aligned.vertices[:, :2]
                cluster_faces = body.faces[face_indices]

                triangles = []
                # NO MINIMUM AREA THRESHOLDS: Preserve all geometric shapes, thin lips, and cutouts
                for f in cluster_faces:
                    pts = v2d[f]
                    poly = Polygon(pts)
                    if poly.is_valid and poly.area > 0:
                        triangles.append(poly)

                if not triangles:
                    continue

                # Merge adjacent coplanar triangles into continuous 2D polygon outlines
                union_poly = unary_union(triangles)
                if union_poly.is_empty:
                    continue

                polygons = union_poly.geoms if hasattr(union_poly, "geoms") else [union_poly]

                for shape_idx, polygon in enumerate(polygons):
                    if polygon.is_empty or polygon.area <= 0:
                        continue

                    # Outer boundary
                    raw_exterior = list(polygon.exterior.coords)
                    contour = [[round(float(x), 4), round(float(y), 4)] for x, y in raw_exterior]
                    if len(contour) > 0 and contour[0] != contour[-1]:
                        contour.append(contour[0])

                    if len(contour) < 3:
                        continue

                    # Inner holes
                    holes = []
                    for interior in polygon.interiors:
                        raw_hole = list(interior.coords)
                        hole_pts = [[round(float(x), 4), round(float(y), 4)] for x, y in raw_hole]
                        if len(hole_pts) >= 3:
                            if hole_pts[0] != hole_pts[-1]:
                                hole_pts.append(hole_pts[0])
                            holes.append(hole_pts)

                    minx, miny, maxx, maxy = polygon.bounds
                    width = round(float(maxx - minx), 4)
                    length = round(float(maxy - miny), 4)

                    if width <= 0 or length <= 0:
                        continue

                    part_id = f"{file_stem}_body_{body_counter}_face_{cluster_idx}_{shape_idx}_{uuid.uuid4().hex[:5]}"
                    part_name = f"{file_stem}_face_angle_{cluster_idx+1}"

                    svg = generate_svg_with_labels(contour, holes=holes, thickness=thickness, radius=None)

                    parts.append(
                        PartItem(
                            part_id=part_id,
                            name=part_name,
                            thickness=thickness,
                            radius=None,
                            contour=contour,
                            holes=holes,
                            bounding_box=BoundingBox(width=width, length=length),
                            svg_path=svg,
                            quantity=1,
                            allow_rotation=True,
                        )
                    )

    return parts


def extract_dxf_true_shapes(
    dxf_path: Path,
    file_stem: str,
    default_thickness: float = 0.0
) -> List[PartItem]:
    """
    Upgraded 2D Pipeline (DWG, DXF via ezdxf):
    - Removes minimum area thresholds.
    - Reads lines, arcs, splines, polylines, circles, ellipses, hatches, and block references (INSERT).
    - Stitches entities into closed 2D loops with outer boundaries and inner holes.
    - Includes default thickness and generates SVG output with text labels.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse DXF file: {str(e)}"
        )

    msp = doc.modelspace()
    lines: List[LineString] = []
    closed_polys: List[Polygon] = []

    def process_entity_collection(entities):
        for entity in entities:
            entity_type = entity.dxftype()

            if entity_type == "INSERT":
                try:
                    process_entity_collection(entity.virtual_entities())
                except Exception:
                    pass
                continue

            try:
                path = ezdxf.path.make_path(entity)
                coords = [(round(float(pt.x), 4), round(float(pt.y), 4)) for pt in path.flattening(distance=0.01)]
                if len(coords) < 2:
                    continue

                if path.is_closed:
                    poly = Polygon(coords)
                    if poly.is_valid and poly.area > 0:
                        closed_polys.append(poly)
                    elif len(coords) >= 3:
                        lines.append(LineString(coords))
                else:
                    lines.append(LineString(coords))
            except Exception:
                pass

    process_entity_collection(msp)

    # Stitch open entities into 2D polygons using polygonize
    stitched_polys = list(polygonize(lines))
    all_polys = closed_polys + stitched_polys

    parts: List[PartItem] = []
    part_counter = 0

    for poly in all_polys:
        if poly.is_empty or poly.area <= 0:
            continue

        part_counter += 1

        # Outer contour
        raw_coords = list(poly.exterior.coords)
        contour = [[round(float(x), 4), round(float(y), 4)] for x, y in raw_coords]
        if len(contour) > 0 and contour[0] != contour[-1]:
            contour.append(contour[0])

        if len(contour) < 3:
            continue

        # Inner holes
        holes = []
        for interior in poly.interiors:
            raw_hole = list(interior.coords)
            hole_pts = [[round(float(x), 4), round(float(y), 4)] for x, y in raw_hole]
            if len(hole_pts) >= 3:
                if hole_pts[0] != hole_pts[-1]:
                    hole_pts.append(hole_pts[0])
                holes.append(hole_pts)

        minx, miny, maxx, maxy = poly.bounds
        width = round(float(maxx - minx), 4)
        length = round(float(maxy - miny), 4)

        if width <= 0 or length <= 0:
            continue

        part_id = f"{file_stem}_shape_{part_counter}_{uuid.uuid4().hex[:6]}"
        part_name = f"{file_stem}_shape_{part_counter}"

        svg = generate_svg_with_labels(contour, holes=holes, thickness=default_thickness, radius=None)

        parts.append(
            PartItem(
                part_id=part_id,
                name=part_name,
                thickness=default_thickness,
                radius=None,
                contour=contour,
                holes=holes,
                bounding_box=BoundingBox(width=width, length=length),
                svg_path=svg,
                quantity=1,
                allow_rotation=True,
            )
        )

    return parts


def group_true_shape_parts(parts: List[PartItem]) -> List[PartItem]:
    """
    Groups identical true-shapes to optimize payload quantity for downstream
    True-Shape Bin Packing algorithms.
    Computes geometric signature (thickness, radius, 2D area, 2D perimeter, bounding box)
    and merges identical shapes into a single PartItem with incremented quantity.
    """
    grouped: dict[tuple, PartItem] = {}

    for part in parts:
        try:
            poly = Polygon(part.contour)
            area = round(float(poly.area), 4)
            perimeter = round(float(poly.length), 4)
        except Exception:
            area = 0.0
            perimeter = 0.0

        t = round(float(part.thickness), 4)
        r = round(float(part.radius), 4) if part.radius is not None else None
        w = round(float(part.bounding_box.width), 4)
        l = round(float(part.bounding_box.length), 4)
        num_holes = len(part.holes)

        if part.allow_rotation:
            key = (t, r, area, perimeter, num_holes, min(w, l), max(w, l))
        else:
            key = (t, r, area, perimeter, num_holes, w, l)

        if key in grouped:
            grouped[key].quantity += part.quantity
        else:
            grouped[key] = PartItem(
                part_id=part.part_id,
                name=part.name,
                thickness=part.thickness,
                radius=part.radius,
                contour=part.contour,
                holes=part.holes,
                bounding_box=BoundingBox(
                    width=key[5] if part.allow_rotation else w,
                    length=key[6] if part.allow_rotation else l,
                ),
                svg_path=part.svg_path,
                quantity=part.quantity,
                allow_rotation=part.allow_rotation,
            )

    return list(grouped.values())


@router.post(
    "/extract",
    response_model=List[PartItem],
    summary="Extract True-Shape 2D contours, curves, and thickness from CAD file",
    description="Extracts all surface angle 2D contours, curved feature radii, material thickness, and inner holes from .dwg, .dxf, .stl, or .obj files."
)
@router.post(
    "",
    response_model=List[PartItem],
    include_in_schema=False
)
async def extract_cad_dimensions(
    file: UploadFile = File(...),
    default_thickness: float = 0.0
) -> List[PartItem]:
    """
    Upload a CAD file (.dwg, .dxf, .stl, .obj) to perform multi-angle True-Shape Extraction.
    Returns a compressed JSON list of PartItem objects with true 2D contours, inner holes,
    calculated radii, material thickness, SVG strings, and merged quantities.
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
            extracted_parts = extract_3d_true_shapes(temp_file_path, file_stem)
        elif file_ext == ".dxf":
            extracted_parts = extract_dxf_true_shapes(temp_file_path, file_stem, default_thickness=default_thickness)
        elif file_ext == ".dwg":
            conversion_dir = temp_dir / "converted_dxf"
            try:
                converted_dxf_path = convert_dwg_to_dxf(temp_file_path, conversion_dir)
                extracted_parts = extract_dxf_true_shapes(converted_dxf_path, file_stem, default_thickness=default_thickness)
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

        return group_true_shape_parts(extracted_parts)


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    parent_dir = Path(__file__).resolve().parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.append(str(parent_dir))

    app = FastAPI(
        title="CAD True-Shape & Curve Extraction Service",
        description="Local server for multi-angle CAD True-Shape & curve extraction router.",
        version="3.0.0",
    )

    app.include_router(router)

    @app.get("/", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": "cad-true-shape-curve-extractor",
            "docs_url": "/docs"
        }

    uvicorn.run(app, host="0.0.0.0", port=8000)
