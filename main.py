"""Chem Editor - Lightweight compound structure editor with Ketcher."""

import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "compounds.json"
KETCHER_DIR = STATIC_DIR / "ketcher"

# ---------------------------------------------------------------------------
# Ketcher check
# ---------------------------------------------------------------------------

def _check_ketcher() -> None:
    if not (KETCHER_DIR / "index.html").exists():
        print("WARNING: Ketcher not found at static/ketcher/.")
        print("  Build it:  cd ketcher-app && npm install && npm run build")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load() -> list[dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(compounds: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(compounds, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Chem Editor")



class CompoundIn(BaseModel):
    name: str = ""
    smiles: str = ""
    molfile: str = ""
    memo: str = ""


# --- Pages ----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# --- CRUD -----------------------------------------------------------------

@app.get("/api/compounds")
async def list_compounds():
    return _load()


@app.post("/api/compounds")
async def add_compound(data: CompoundIn):
    compounds = _load()

    name = data.name.strip() or f"Compound {len(compounds) + 1}"
    formula = ""
    mw = 0.0

    # Compute formula & MW with RDKit
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        mol = None
        if data.molfile:
            mol = Chem.MolFromMolBlock(data.molfile)
        if mol is None and data.smiles:
            mol = Chem.MolFromSmiles(data.smiles)
        if mol is not None:
            formula = Chem.rdMolDescriptors.CalcMolFormula(mol)
            mw = round(Descriptors.ExactMolWt(mol), 4)
    except Exception:
        pass

    compound = {
        "id": str(uuid.uuid4()),
        "name": name,
        "smiles": data.smiles,
        "molfile": data.molfile,
        "formula": formula,
        "mw": mw,
        "memo": data.memo,
        "created_at": datetime.now().isoformat(),
    }
    compounds.append(compound)
    _save(compounds)
    return compound


@app.delete("/api/compounds/{compound_id}")
async def delete_compound(compound_id: str):
    compounds = _load()
    before = len(compounds)
    compounds = [c for c in compounds if c["id"] != compound_id]
    if len(compounds) == before:
        raise HTTPException(404, "Not found")
    _save(compounds)
    return {"status": "ok"}


@app.post("/api/save")
async def force_save():
    """Explicit save (data is already auto-saved on every mutation)."""
    compounds = _load()
    _save(compounds)
    return {"status": "ok", "count": len(compounds)}


# --- SVG ------------------------------------------------------------------

@app.get("/api/compounds/{compound_id}/svg")
async def compound_svg(compound_id: str):
    compounds = _load()
    compound = next((c for c in compounds if c["id"] == compound_id), None)
    if not compound:
        raise HTTPException(404)

    try:
        from rdkit import Chem
        from rdkit.Chem.Draw import rdMolDraw2D

        mol = None
        if compound.get("molfile"):
            mol = Chem.MolFromMolBlock(compound["molfile"])
        if mol is None and compound.get("smiles"):
            mol = Chem.MolFromSmiles(compound["smiles"])
            if mol is not None:
                from rdkit.Chem import AllChem
                AllChem.Compute2DCoords(mol)

        if mol is None:
            raise HTTPException(400, "Cannot parse molecule")

        drawer = rdMolDraw2D.MolDraw2DSVG(280, 180)
        opts = drawer.drawOptions()
        opts.addStereoAnnotation = True
        opts.clearBackground = True
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()
        return Response(content=svg, media_type="image/svg+xml")

    except ImportError:
        raise HTTPException(500, "RDKit not available")


# --- Export ---------------------------------------------------------------

@app.get("/api/export/csv")
async def export_csv():
    compounds = _load()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "SMILES", "Formula", "MW", "Memo", "Created"])
    for c in compounds:
        writer.writerow([
            c["name"],
            c["smiles"],
            c.get("formula", ""),
            c.get("mw", ""),
            c.get("memo", ""),
            c["created_at"],
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compounds.csv"},
    )


@app.get("/api/export/sdf")
async def export_sdf():
    compounds = _load()
    blocks: list[str] = []

    for c in compounds:
        molblock = c.get("molfile", "")
        if not molblock or "M  END" not in molblock:
            # Try to generate from SMILES via RDKit
            try:
                from rdkit import Chem
                from rdkit.Chem import AllChem

                mol = Chem.MolFromSmiles(c.get("smiles", ""))
                if mol is not None:
                    AllChem.Compute2DCoords(mol)
                    molblock = Chem.MolToMolBlock(mol)
            except Exception:
                continue
            if not molblock:
                continue

        entry = molblock.rstrip("\n") + "\n"
        entry += f">  <Name>\n{c['name']}\n\n"
        entry += f">  <SMILES>\n{c.get('smiles', '')}\n\n"
        if c.get("formula"):
            entry += f">  <Formula>\n{c['formula']}\n\n"
        if c.get("mw"):
            entry += f">  <MW>\n{c['mw']}\n\n"
        if c.get("memo"):
            entry += f">  <Memo>\n{c['memo']}\n\n"
        entry += "$$$$\n"
        blocks.append(entry)

    return Response(
        content="".join(blocks),
        media_type="chemical/x-mdl-sdfile",
        headers={"Content-Disposition": "attachment; filename=compounds.sdf"},
    )


# --- Static files (must be last) -----------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    DATA_DIR.mkdir(exist_ok=True)
    _check_ketcher()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
