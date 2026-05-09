 from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import google.generativeai as genai
import uvicorn
from PIL import Image
import io

# =============================
# Configuration API
# =============================

genai.configure(api_key="AIzaSyDcl9pksEfR4sTNFAOenLJ_jCPLX4_6CVQ")

# =============================
# Charger le modèle Gemma
# =============================

model = genai.GenerativeModel("gemma-3-27b-it")

# =============================
# Initialiser FastAPI
# =============================

app = FastAPI(
    title="Gemma AI API",
    description="API FastAPI utilisant Gemma 3 pour analyser une image",
    version="1.0"
)

# =============================
# Prompt par défaut
# =============================

PROMPT = """
Tu es un expert en pièces détachées automobiles. Analyse cette image et réponds EXCLUSIVEMENT au format suivant (une ligne par champ, sans texte avant ou après) :

Nom de la pièce : [nom exact technique]
Description : [description courte : fonction, emplacement, caractéristiques visibles]
Marque/Véhicule compatible : [marques et modèles compatibles, ou "Universel"]

Ne rajoute aucune introduction, conclusion, ou texte hors de ces 3 lignes
"""

# =============================
# Route test
# =============================

@app.get("/")
def home():
    return {"message": "Gemma FastAPI server is running"}

# =============================
# Endpoint analyse image
# =============================

@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):

    # lire l'image envoyée
    image_bytes = await file.read()

    # convertir en image PIL
    image = Image.open(io.BytesIO(image_bytes))

    # envoyer image + prompt au modèle
    response = model.generate_content([PROMPT, image])

    return {
        "filename": file.filename,
        "analysis": response.text
    }

# =============================
# Lancer le serveur
# =============================

if __name__ == "__main__":
    uvicorn.run(
        "vlm:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )