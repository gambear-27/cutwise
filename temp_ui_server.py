import os
import sys
from pathlib import Path

# Ensure paths are set
_current_dir = Path(__file__).resolve().parent
for _p in [_current_dir, _current_dir.parent]:
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from cad_router import router

app = FastAPI(
    title="CAD Geometry Extraction - Temporary Testing UI",
    description="Interactive UI to test DWG, DXF, STL, OBJ True-Shape, Curve & Thickness extraction microservice.",
    version="3.0.0"
)

# Include the CAD geometry router
app.include_router(router)

# Embedded Single-Page Application (HTML + CSS + Vanilla JS)
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CAD True-Shape & Curve Extractor UI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --surface: #111827;
      --surface-border: #1f2937;
      --card: #182234;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.2);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --danger: #ef4444;
      --danger-bg: rgba(239, 68, 68, 0.1);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    body {
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--surface-border);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .brand-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #3b82f6, #10b981);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.1rem;
      color: #fff;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }

    .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #fff, #93c5fd);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .badge-temp {
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      background: rgba(245, 158, 11, 0.15);
      color: #f59e0b;
      border: 1px solid rgba(245, 158, 11, 0.3);
      font-weight: 500;
    }

    main {
      flex: 1;
      max-width: 1240px;
      width: 100%;
      margin: 0 auto;
      padding: 2rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }

    .hero-text {
      text-align: center;
      margin-bottom: 0.5rem;
    }

    .hero-text h1 {
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 0.5rem;
    }

    .hero-text p {
      color: var(--text-muted);
      font-size: 1rem;
      max-width: 700px;
      margin: 0 auto;
    }

    .upload-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 2rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }

    .dropzone {
      border: 2px dashed #374151;
      border-radius: 12px;
      padding: 3rem 2rem;
      text-align: center;
      background: rgba(24, 34, 52, 0.3);
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
    }

    .dropzone:hover, .dropzone.dragover {
      border-color: var(--primary);
      background: rgba(59, 130, 246, 0.08);
      transform: translateY(-2px);
    }

    .dropzone-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
      display: inline-block;
    }

    .dropzone h3 {
      font-size: 1.15rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
    }

    .dropzone p {
      color: var(--text-muted);
      font-size: 0.875rem;
    }

    .format-pills {
      display: flex;
      justify-content: center;
      gap: 0.5rem;
      margin-top: 1rem;
    }

    .pill {
      font-size: 0.75rem;
      background: rgba(255, 255, 255, 0.06);
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: #93c5fd;
      font-family: 'JetBrains Mono', monospace;
    }

    .file-input {
      display: none;
    }

    .actions-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 1.5rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--surface-border);
    }

    .selected-file-info {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.9rem;
    }

    .file-name {
      font-weight: 600;
      color: #fff;
    }

    .file-size {
      color: var(--text-muted);
      font-size: 0.8rem;
    }

    .btn {
      background: var(--primary);
      color: #fff;
      border: none;
      padding: 0.75rem 1.75rem;
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.95rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
      box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35);
    }

    .btn:hover:not(:disabled) {
      background: var(--primary-hover);
      transform: translateY(-1px);
    }

    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
    }

    .status-panel {
      display: none;
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 12px;
      padding: 1.5rem;
      align-items: center;
      gap: 1rem;
    }

    .spinner {
      width: 24px;
      height: 24px;
      border: 3px solid rgba(59, 130, 246, 0.2);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .error-alert {
      display: none;
      background: var(--danger-bg);
      border: 1px solid var(--danger);
      color: #fca5a5;
      padding: 1rem 1.25rem;
      border-radius: 10px;
      font-size: 0.9rem;
      line-height: 1.5;
    }

    .results-container {
      display: none;
      flex-direction: column;
      gap: 1.5rem;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }

    .stat-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 12px;
      padding: 1.25rem;
    }

    .stat-label {
      color: var(--text-muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }

    .stat-value {
      font-size: 1.6rem;
      font-weight: 700;
      color: #fff;
    }

    .table-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 14px;
      overflow: hidden;
    }

    .card-header {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--surface-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .card-header h2 {
      font-size: 1.1rem;
      font-weight: 600;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    th {
      background: rgba(15, 23, 42, 0.6);
      color: var(--text-muted);
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.85rem 1.25rem;
      border-bottom: 1px solid var(--surface-border);
    }

    td {
      padding: 1rem 1.25rem;
      font-size: 0.9rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }

    tr:last-child td {
      border-bottom: none;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    .dim-tag {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      background: rgba(59, 130, 246, 0.12);
      color: #93c5fd;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      font-weight: 600;
    }

    .thick-tag {
      display: inline-flex;
      align-items: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      font-weight: 600;
    }

    .radius-tag {
      display: inline-flex;
      align-items: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      background: rgba(168, 85, 247, 0.15);
      color: #c084fc;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      font-weight: 600;
    }

    .qty-tag {
      font-weight: 700;
      color: var(--accent);
      background: rgba(16, 185, 129, 0.15);
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.85rem;
    }

    .json-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 14px;
      overflow: hidden;
    }

    pre {
      background: #060911;
      padding: 1.25rem;
      color: #e2e8f0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      line-height: 1.6;
      max-height: 380px;
      overflow-y: auto;
    }

    .copy-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #fff;
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s;
    }

    .copy-btn:hover {
      background: rgba(255, 255, 255, 0.18);
    }

    .preview-canvas-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 14px;
      padding: 1.5rem;
    }

    .preview-canvas-card h3 {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--text-muted);
    }

    .preview-board {
      width: 100%;
      min-height: 260px;
      background: #070b14;
      border: 1px solid #1f293d;
      border-radius: 8px;
      position: relative;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      gap: 1.25rem;
      overflow: hidden;
      background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 20px 20px;
    }

    .svg-wrapper {
      width: 200px;
      height: 160px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .svg-wrapper svg {
      width: 100%;
      height: 100%;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-icon">📐</div>
      <div>
        <div class="brand-title">CAD True-Shape & Curve Extraction</div>
      </div>
    </div>
    <span class="badge-temp">True-Shape & Curve Engine v3.0</span>
  </header>

  <main>
    <div class="hero-text">
      <h1>Extract All Surface Angles, Curves & Thickness</h1>
      <p>Scan all surface angles across 3D models, measure material thickness, reconstruct curved radii (cylinders, holes, fillets), and output labeled SVG profiles.</p>
    </div>

    <!-- Upload Box -->
    <div class="upload-card">
      <div class="dropzone" id="dropzone">
        <input type="file" id="fileInput" class="file-input" accept=".dwg,.dxf,.stl,.obj">
        <div class="dropzone-icon">📁</div>
        <h3>Drop your CAD file here, or browse</h3>
        <p>Supports AutoCAD DWG, DXF, 3D STL & Wavefront OBJ</p>
        <div class="format-pills">
          <span class="pill">.DWG</span>
          <span class="pill">.DXF</span>
          <span class="pill">.STL</span>
          <span class="pill">.OBJ</span>
        </div>
      </div>

      <div class="actions-bar">
        <div class="selected-file-info" id="selectedFileInfo">
          <span style="color: var(--text-muted);">No file selected yet</span>
        </div>
        <button id="extractBtn" class="btn" disabled>
          <span>Extract All Profiles & Curves</span>
          <span>⚡</span>
        </button>
      </div>
    </div>

    <!-- Processing Panel -->
    <div class="status-panel" id="statusPanel">
      <div class="spinner"></div>
      <div>
        <div style="font-weight: 600; font-size: 0.95rem;" id="statusText">Scanning all surface angles & measuring curves...</div>
        <div style="color: var(--text-muted); font-size: 0.8rem;">Relaxing normal tolerances, measuring thickness, fitting curved radii, and rendering SVG profiles</div>
      </div>
    </div>

    <!-- Error Alert -->
    <div class="error-alert" id="errorAlert"></div>

    <!-- Results Display -->
    <div class="results-container" id="resultsContainer">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Extracted Profiles & Curves</div>
          <div class="stat-value" id="statGroups">0</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Parts (Merged Quantity)</div>
          <div class="stat-value" style="color: var(--accent);" id="statTotalQty">0</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Input File</div>
          <div class="stat-value" style="font-size: 1.1rem; line-height: 2rem;" id="statFilename">-</div>
        </div>
      </div>

      <!-- 2D True-Shape SVG Preview -->
      <div class="preview-canvas-card">
        <h3>2D True-Shape SVG Vector Visualizer (With Thickness & Curve Labels)</h3>
        <div class="preview-board" id="previewBoard">
          <span style="color: var(--text-muted); font-size: 0.85rem;">Interactive preview loaded below</span>
        </div>
      </div>

      <!-- Parts Table -->
      <div class="table-card">
        <div class="card-header">
          <h2>Extracted Profile & Curve Cut-List</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Part Name / ID</th>
              <th>Thickness (Z-axis)</th>
              <th>Radius (Curved)</th>
              <th>Bounding Box (W × L)</th>
              <th>Holes / Cutouts</th>
              <th>Quantity</th>
              <th>Rotation Allowed</th>
            </tr>
          </thead>
          <tbody id="partsTableBody">
          </tbody>
        </table>
      </div>

      <!-- Raw JSON Box -->
      <div class="json-card">
        <div class="card-header">
          <h2>Unified JSON Output</h2>
          <button class="copy-btn" id="copyJsonBtn">Copy JSON</button>
        </div>
        <pre><code id="jsonCode">// JSON response will appear here</code></pre>
      </div>
    </div>
  </main>

  <script>
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const extractBtn = document.getElementById('extractBtn');
    const selectedFileInfo = document.getElementById('selectedFileInfo');
    const statusPanel = document.getElementById('statusPanel');
    const statusText = document.getElementById('statusText');
    const errorAlert = document.getElementById('errorAlert');
    const resultsContainer = document.getElementById('resultsContainer');
    const partsTableBody = document.getElementById('partsTableBody');
    const jsonCode = document.getElementById('jsonCode');
    const copyJsonBtn = document.getElementById('copyJsonBtn');
    const previewBoard = document.getElementById('previewBoard');

    let currentFile = null;
    let lastJsonData = null;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });

    function formatBytes(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function handleFileSelect(file) {
      currentFile = file;
      selectedFileInfo.innerHTML = `
        <span style="font-size: 1.2rem;">📄</span>
        <div>
          <div class="file-name">${file.name}</div>
          <div class="file-size">${formatBytes(file.size)}</div>
        </div>
      `;
      extractBtn.disabled = false;
      errorAlert.style.display = 'none';
    }

    extractBtn.addEventListener('click', async () => {
      if (!currentFile) return;

      statusPanel.style.display = 'flex';
      errorAlert.style.display = 'none';
      resultsContainer.style.display = 'none';
      extractBtn.disabled = true;

      const formData = new FormData();
      formData.append('file', currentFile);

      try {
        const response = await fetch('/cad/extract', {
          method: 'POST',
          body: formData
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || `Server returned error ${response.status}`);
        }

        lastJsonData = data;
        renderResults(data);
      } catch (err) {
        errorAlert.textContent = 'Extraction Failed: ' + err.message;
        errorAlert.style.display = 'block';
      } finally {
        statusPanel.style.display = 'none';
        extractBtn.disabled = false;
      }
    });

    function renderResults(parts) {
      resultsContainer.style.display = 'flex';
      
      document.getElementById('statGroups').textContent = parts.length;
      const totalQty = parts.reduce((acc, p) => acc + (p.quantity || 1), 0);
      document.getElementById('statTotalQty').textContent = totalQty;
      document.getElementById('statFilename').textContent = currentFile.name;

      partsTableBody.innerHTML = '';
      if (parts.length === 0) {
        partsTableBody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">
              No shapes extracted from this file.
            </td>
          </tr>
        `;
      } else {
        parts.forEach(p => {
          const tr = document.createElement('tr');
          const bbox = p.bounding_box || p.dimensions || {};
          const holes = p.holes || [];
          const radStr = p.radius !== null && p.radius !== undefined ? `<span class="radius-tag">R: ${p.radius}</span>` : '<span style="color: var(--text-muted);">-</span>';
          tr.innerHTML = `
            <td>
              <div style="font-weight: 600;">${p.name || p.part_id}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${p.part_id}</div>
            </td>
            <td>
              <span class="thick-tag">T: ${p.thickness}</span>
            </td>
            <td>
              ${radStr}
            </td>
            <td>
              <span class="dim-tag">${bbox.width} × ${bbox.length}</span>
            </td>
            <td>
              <span style="font-family: monospace; color: #9ca3af;">${holes.length} hole(s)</span>
            </td>
            <td>
              <span class="qty-tag">${p.quantity}</span>
            </td>
            <td>
              <span style="color: ${p.allow_rotation ? '#34d399' : '#f87171'}; font-weight: 500;">
                ${p.allow_rotation ? '✓ Yes' : '✕ No'}
              </span>
            </td>
          `;
          partsTableBody.appendChild(tr);
        });
      }

      // Render SVG previews
      previewBoard.innerHTML = '';
      if (parts.length > 0) {
        parts.forEach(p => {
          const container = document.createElement('div');
          container.style.cssText = `
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(24, 34, 52, 0.75);
            border: 1px solid var(--surface-border);
            border-radius: 10px;
            padding: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          `;

          const svgWrapper = document.createElement('div');
          svgWrapper.className = 'svg-wrapper';
          if (p.svg_path) {
            svgWrapper.innerHTML = p.svg_path;
          } else {
            svgWrapper.innerHTML = '<span style="color: var(--text-muted);">No SVG</span>';
          }

          container.appendChild(svgWrapper);

          const label = document.createElement('div');
          label.style.cssText = `
            font-size: 0.75rem;
            font-family: monospace;
            color: #93c5fd;
            margin-top: 8px;
            font-weight: 600;
          `;
          const bbox = p.bounding_box || p.dimensions || {};
          label.textContent = `${bbox.width}×${bbox.length} (T: ${p.thickness})`;
          container.appendChild(label);

          previewBoard.appendChild(container);
        });
      } else {
        previewBoard.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem;">No 2D parts to preview</span>';
      }

      jsonCode.textContent = JSON.stringify(parts, null, 2);
    }

    copyJsonBtn.addEventListener('click', () => {
      if (!lastJsonData) return;
      navigator.clipboard.writeText(JSON.stringify(lastJsonData, null, 2)).then(() => {
        copyJsonBtn.textContent = 'Copied!';
        setTimeout(() => copyJsonBtn.textContent = 'Copy JSON', 2000);
      });
    });
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the temporary interactive testing web application."""
    return HTMLResponse(content=HTML_CONTENT)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print("\n" + "=" * 60)
    print("Starting Temporary CAD Extraction UI Server...")
    print(f"Open your browser and visit:")
    print(f"http://localhost:{port}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=port)
